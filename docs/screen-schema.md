# PufferFish Screen Schema

A **screen** is any discrete step a user encounters when navigating a product artifact — a UI screen, a section of a PRD, a pricing tier, a form, or a step in a flow.

## Schema

```json
{
  "id": "screen_01",
  "name": "Route Selection",
  "content": "Choose your bridge route. Fast (2 min, 0.3% fee) or Economy (8 min, 0.1% fee).",
  "available_actions": ["select_fast", "select_economy", "view_details", "go_back", "abandon"],
  "requires_prior_knowledge": ["what a bridge route is", "fee vs speed tradeoff"]
}
```

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier. Use `screen_01`, `screen_02`, etc. |
| `name` | string | Yes | Short human-readable name (2–5 words) |
| `content` | string | Yes | What the user actually sees — exact copy, labels, options. Be faithful to the product. |
| `available_actions` | array of strings | Yes | Actions available from this screen. Always include `"abandon"`. Use snake_case. |
| `requires_prior_knowledge` | array of strings | No | Concepts or knowledge assumed by this screen. Used to calibrate how confused novice agents will be. |

## Conventions

- `"abandon"` must always be in `available_actions` — users can always leave
- For non-UI artifacts (PRDs, docs, changelogs), use generic actions: `["continue", "re_read", "abandon", "ask_question"]`
- `content` should be the actual text/copy the user reads, not a description of it
- Target 3–8 screens for most features; more for complex multi-step flows
- Order screens in the order a user would encounter them (the traversal engine runs them sequentially)

## Example: UI flow

```json
[
  {
    "id": "screen_01",
    "name": "Landing",
    "content": "Bridge your tokens across chains. Connect your wallet to get started.",
    "available_actions": ["connect_wallet", "learn_more", "abandon"],
    "requires_prior_knowledge": []
  },
  {
    "id": "screen_02",
    "name": "Token & Amount",
    "content": "Select token: USDC. Amount: [input field]. From: Arbitrum → To: Base.",
    "available_actions": ["enter_amount", "change_token", "change_chain", "abandon"],
    "requires_prior_knowledge": ["what USDC is", "what Arbitrum and Base are"]
  },
  {
    "id": "screen_03",
    "name": "Route Selection",
    "content": "Choose your bridge route. Fast (2 min, 0.3% fee) or Economy (8 min, 0.1% fee).",
    "available_actions": ["select_fast", "select_economy", "view_details", "go_back", "abandon"],
    "requires_prior_knowledge": ["what a bridge route is", "fee vs speed tradeoff"]
  },
  {
    "id": "screen_04",
    "name": "Confirmation",
    "content": "You are bridging 100 USDC from Arbitrum to Base via Fast route. Fee: 0.3 USDC. Gas: ~$0.50. Estimated time: 2 minutes. [Confirm]",
    "available_actions": ["confirm", "go_back", "abandon"],
    "requires_prior_knowledge": ["what gas fees are", "why there are two separate fees"]
  }
]
```

## Example: PRD / document artifact

For non-UI artifacts, each section of the document becomes a "screen":

```json
[
  {
    "id": "screen_01",
    "name": "Problem Statement",
    "content": "Users currently cannot bridge tokens across more than 3 chains in a single transaction...",
    "available_actions": ["continue", "re_read", "abandon", "ask_question"],
    "requires_prior_knowledge": []
  }
]
```
