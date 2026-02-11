import os
import json
import openai
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")


print("Connecting to MongoDB at:", MONGODB_URI)
client = MongoClient(MONGODB_URI)
db = client["arcum-qa"]

# Collections
merchants_col = db["merchant_data"]
metrics_col   = db["acn_metrics_data"]

clients_cursor = merchants_col.find({"name": "ACN"})
merchant_ids = [c.get("merchant_id") for c in clients_cursor if c.get("merchant_id")]
print(f"Processing {len(merchant_ids)} ACN merchants")

models = ["gpt-4o-mini"]




field_definitions = """
Field Definitions:
- year_month: month of data record
- total_volume: merchant's monthly processing volume (USD)
- effective_rate: merchant’s processing fee rate (%)
- chargeback_rate: total chargebacks as a percentage of volume
- total_transactions: number of merchant transactions per month
- month_over_threemonth_vol: merchant’s monthly volume growth rate (%)
- support_count: number of monthly merchant support interactions
- tenure: the number of months that the merchant has been processing with our client 
"""

input_example = """
Input Data Example:
Merchant Metrics:
- Volume: $50,000
- Effective rate: 4%
- Chargebacks (%): 2%
- Transactions: 200
- Monthly volume growth: -12%
- Support calls: 3
- Tenure: 8
"""
# Updated system instruction
system_instruction = """
You are a payments retention analyst at Arcum, an AI-powered platform that helps payment processors and ISOs predict and prevent merchant churn. Arcum’s clients manage portfolios of merchants processing card payments.

Given merchant transactional and behavioral data, generate clear and actionable outputs:

Outputs:
1. Explanation (1 sentence):
Clearly state why this merchant is at risk of churn (without saying this merchant is at risk of leaving because...this is implied), referencing specific data trends (e.g., declining volume, increasing chargebacks, or rising support interactions, rise in effective rate (price).
2. Suggestion (1 sentence):
Recommend a targeted action the account manager should take to proactively mitigate churn risk (e.g., outreach, pricing adjustment, product upgrade, proactive support).

3. Reason Category: Choose EXACTLY ONE from these 8 categories based on the primary underlying cause:
   - agent (issues with account management or support quality) 
   - pricing (merchant dissatisfaction related to pricing or rates) 
   - product (terminal issues or technology challenges) 
   - service (issues with customer service or support) 
   - seasonality (typical seasonal fluctuations)
   - microeconomic (local market conditions impacting merchant)
   - macroeconomic (broader economic conditions affecting industry/region) 
   - cashflow (merchant-specific financial strain) 

4. Suggested Action: Provide exactly one recommended action aligned with your chosen reason:
-Revise price (adjust pricing or offer incentives)
-Revise product (upgrade or replace terminal/product)
-call (make direct phone outreach)
-visit (schedule in-person visit from sales or service rep)
-MCA/loan (offer merchant cash advance or financial support)
-chargeback mitigation (provide solutions to reduce chargebacks)
-email (engage via targeted email communication)

IMPORTANT:
You MUST select the Reason from ONLY the 8 categories listed. Never write 'chargeback mitigation' or any Suggested Action in the Reason field.
"""

for merchant_doc in merchants_col.find({"name": "ACN"}):
    target_mid = merchant_doc.get("merchant_id")
    term_date  = merchant_doc.get("term_date")
    if not (target_mid and term_date):
        continue
    print(f"\n--- Processing MID: {target_mid} for term_date: {term_date} ---")

    d = metrics_col.find_one({"mid": target_mid, "year_month": term_date})
    if not d:
        print(f"No metrics for MID {target_mid} at month {term_date}, skipping")
        continue

    record = {
        "year_month": d.get("year_month"),
        "total_volume": d.get("total_volume"),
        "effective_rate": round(d.get("price", 0) * 100, 2) if d.get("price") is not None else None,
        "chargeback_rate": round((d.get("activitychargebackamount", 0) / (d.get("total_volume", 1))) * 100, 2) if d.get("total_transactions") else None,
        "transactions": d.get("total_transactions"),
        "month_over_threemonth_vol": d.get("month_over_threemonth_vol"),
        "support_count": d.get("support_count"),
        "tenure": (
            d.get("tenure") + 1
            if d.get("tenure") and d.get("tenure") > 0
            else d.get("tenure") or 0
        )
    }
    metrics_block = "\n".join(f"{k}: {v}" for k, v in record.items())

    user_prompt = f"""Arcum Churn Reason + Suggestion Model Prompt

{field_definitions}
{input_example}

Merchant MID: {target_mid}  Month: {term_date}
{metrics_block}

Output format:
Reason_Detailed: <text>
Suggest_Detailed: <text>
Reason: <category>
Suggested: <action>
"""

    resp = openai.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0.3
    )
    out = resp.choices[0].message.content.strip()
    print(f"GPT output for MID {target_mid}, {term_date}:\n{out}\n")


    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    rd = lines[0].split(":",1)[1].strip()
    sd = lines[1].split(":",1)[1].strip()
    rc = lines[2].split(":",1)[1].strip()
    sa = lines[3].split(":",1)[1].strip()

    result = merchants_col.update_one(
        {"_id": merchant_doc["_id"]},
        {"$set": {
            "reason_detailed": rd,
            "suggested_detailed": sd,
            "reason": rc,
            "suggested": sa
        }}
    )
    allowed_reasons = [
        "agent", "pricing", "product", "service",
        "seasonality", "microeconomic", "macroeconomic", "cashflow"
    ]

    if rc not in allowed_reasons:
        print(f"⚠️ Warning: Invalid Reason '{rc}' returned. Consider re-prompting or defaulting.") 
    print(f"Updated merchant_data _id {merchant_doc['_id']}: matched {result.matched_count}, modified {result.modified_count}")

  
    usage = resp.usage
    print(f"Tokens used: prompt {usage.prompt_tokens}, completion {usage.completion_tokens}, total {usage.total_tokens}")

    print(f"Finished processing MID {target_mid} for {term_date}")


