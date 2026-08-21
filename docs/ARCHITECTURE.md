# Architecture

LFM2.5-ModelRouter separates stable capability learning from live decision state and deployment feedback.

```text
query + candidate profile
        |
        v
offline outcome predictor
  quality / tokens / latency / failure / uncertainty
        |
        v
runtime optimizer <--- live prices, availability, preferences, constraints
        |
        v
selected action
        |
        v
observed feedback ---> online residual adapter and drift tracking
```

## Offline predictor

The offline model scores candidate configurations independently. Its primary inputs are:

- An LFM2.5 query representation.
- Structured candidate metadata.
- A sparse behavioral probe profile.
- Optional reasoning mode and output budget.

It predicts quantities that remain meaningful when prices change: success/quality, token usage, latency, failures, and uncertainty.

## Runtime optimizer

The optimizer filters invalid candidates and calculates expected utility from current state. Prices and availability are external inputs, not permanent training labels.

Named user modes are presets over a continuous preference space:

- Intelligence emphasizes expected quality.
- Balanced trades quality against cost and latency.
- Cost selects the cheapest action likely to meet a configured success threshold.

## Online adapter

Deployment exposes only the selected model's outcome. The first online design will combine the shared offline prior with discounted per-model linear residuals, uncertainty-aware exploration, and a budget pacer.

## Open candidate set

The registry can add or remove models without resizing a fixed classifier. A new model is initialized from metadata and a small probe set, then receives bounded live exploration.

See [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) for implementation order and completion gates.
