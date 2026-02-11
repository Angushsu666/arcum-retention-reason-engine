---

# Arcum AI Churn Intelligence Engine

Production-grade AI enrichment pipeline for merchant retention.

This system transforms raw transactional data into structured churn explanations and actionable retention strategies using LLMs.

---

## Problem

Payment processors can predict which merchants are likely to churn, but risk scores alone are not actionable.

Account managers need:

* A clear explanation of why a merchant is at risk
* A categorized primary cause
* A specific operational action

Manually interpreting metrics such as volume decline, pricing changes, chargebacks, support interactions, and tenure does not scale.

---

## Solution

This repository implements an AI-powered enrichment layer that:

1. Extracts structured merchant signals from MongoDB
2. Computes business metrics (effective rate, chargeback %, growth rates)
3. Sends only relevant fields to GPT-4.1 / GPT-4o-mini
4. Generates:

   * Reason_Detailed
   * Suggest_Detailed
   * Reason (1 of 8 categories)
   * Suggested (1 allowed action)
5. Writes structured results back into MongoDB for UI and analytics consumption

The system bridges predictive ML outputs with operational execution.

---

## Architecture

MongoDB (merchant_data)
→ match merchant_id + term_date
→ MongoDB (acn_metrics_data)
→ metric normalization layer
→ prompt construction
→ OpenAI API
→ structured response parsing
→ MongoDB update

---

## Key Engineering Decisions

### 1️⃣ Cost Control

* Switched between GPT-4.1 and GPT-4o-mini depending on quality needs
* Reduced prompt token size by sending only relevant features
* Measured per-call token usage for budget planning

Example batch:

* 381 merchants
* ~0.80 USD per full ACN run (GPT-4.1 test)

---

### 2️⃣ Deterministic Output Structure

Prompt enforces:

```
Reason_Detailed:
Suggest_Detailed:
Reason:
Suggested:
```

Strict validation ensures:

* Reason must be one of 8 categories
* Suggested must be one of allowed actions

Prevents UI-breaking outputs.

---

### 3️⃣ Data Normalization Layer

Derived metrics computed before LLM call:

* Effective rate = price * 100
* Chargeback rate = chargeback_amount / total_volume
* Tenure optionally adjusted
* Growth metrics passed directly from MongoDB

This keeps the model focused on reasoning, not arithmetic.

---

### 4️⃣ Database Integrity

* Updates performed via `_id`
* Ensures month-level consistency (merchant_id + term_date match)
* Avoids cross-month contamination

---

## Reason Categories

Internal:

* agent
* pricing
* product
* service

External:

* seasonality
* microeconomic
* macroeconomic
* cashflow

---

## Suggested Actions

* Revise price
* Revise product
* call
* visit
* MCA/loan
* chargeback mitigation
* email

---

## 🔐 Security Practices

* Secrets stored in `.env`
* `.env` excluded via `.gitignore`
* API keys rotated when exposed
* GitHub push protection enforced

---

## Business Impact

This system enables:

Predictive model output
→ Interpretable explanation
→ Categorized churn reason
→ Account manager action

It operationalizes AI within merchant portfolio management.

---

## Scalability

Designed to support:

* Multi-company ingestion
* Scheduled monthly refresh
* Model version comparison
* Async batch processing
* Prompt version control
* Cost-performance benchmarking

---

## Why This Matters

Most churn systems stop at prediction.

This system closes the loop:
AI signal → Human explanation → Operational execution.

It demonstrates:

* Backend data engineering
* LLM integration
* Cost-aware AI deployment
* Production-safe database writes
* Structured AI governance

