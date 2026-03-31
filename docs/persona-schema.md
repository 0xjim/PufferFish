# PufferFish Persona Schema

A **persona** is an agent that navigates the product flow. Personas are defined in JSON library files under `backend/personas/`.

## Schema

```json
{
  "agent_id": "defi_novice_03",
  "cohort": "defi",
  "name": "Marcus",
  "bio": "Got into crypto 6 months ago...",
  "persona": "Cautious and easily confused by jargon...",
  "domain_literacy": "low",
  "mental_model": "Thinks bridging moves tokens from one wallet address to another...",
  "task": "Bridge 100 USDC from Ethereum mainnet to Arbitrum...",
  "entry_context": "Found this app via a YouTube tutorial. Has never used a bridge before.",
  "karma": 100,
  "friend_count": 45,
  "follower_count": 60,
  "statuses_count": 120,
  "age": 24,
  "gender": "male",
  "mbti": "ISFJ",
  "country": "UK",
  "profession": "Graphic designer",
  "interested_topics": ["crypto basics", "DeFi intro"]
}
```

## Fields

### Core (required for traversal)

| Field | Type | Description |
|---|---|---|
| `agent_id` | string | Unique identifier, e.g. `defi_novice_03` |
| `cohort` | string | Library this persona belongs to: `defi`, `saas_b2b`, `devtools`, `consumer` |
| `name` | string | Human-readable name |
| `bio` | string | Short background description (1–3 sentences) |
| `persona` | string | Personality, decision-making style, emotional tendencies |

### PufferFish traversal fields (new)

| Field | Type | Description |
|---|---|---|
| `domain_literacy` | string | `"low"` \| `"medium"` \| `"high"` — how well they understand the domain |
| `mental_model` | string | How they think the product works. Include misconceptions. This is the key signal for novice confusion. |
| `task` | string | The specific goal they are trying to accomplish in this simulation |
| `entry_context` | string | How they arrived at the product. Sets expectations and priors. |

### Social/OASIS fields (optional, preserved for compatibility)

| Field | Type | Default | Description |
|---|---|---|---|
| `karma` | int | 1000 | Reddit-style karma |
| `friend_count` | int | 100 | Twitter following count |
| `follower_count` | int | 150 | Twitter follower count |
| `statuses_count` | int | 500 | Number of posts |
| `age` | int | null | Age |
| `gender` | string | null | Gender |
| `mbti` | string | null | MBTI personality type |
| `country` | string | null | Country |
| `profession` | string | null | Profession |
| `interested_topics` | array | [] | Topics of interest |

## Available persona libraries

| File | Cohort ID | Personas |
|---|---|---|
| `backend/personas/defi.json` | `defi` | Crypto native (high literacy), Intermediate bridger (medium), DeFi novice (low), Institutional (high, compliance-focused) |
| `backend/personas/saas_b2b.json` | `saas_b2b` | *(v0.2)* Champion buyer, end user, IT admin, economic buyer |
| `backend/personas/devtools.json` | `devtools` | *(v0.2)* Senior engineer, junior dev, DevOps, non-technical stakeholder |
| `backend/personas/consumer.json` | `consumer` | *(v0.2)* Early adopter, mainstream user, reluctant adopter |

## Mental model guidance

The `mental_model` field is the most important signal for generating realistic novice confusion. Write it from the agent's perspective — what do they believe is true, even if wrong?

**Good:**
> "Thinks bridging moves tokens from one wallet address to another — doesn't understand gas fees are separate from bridge fees. Believes USDC on Arbitrum is the same as USDC on Ethereum."

**Too vague:**
> "Doesn't understand DeFi very well."

## Contributing persona libraries

Community-contributed libraries are welcome via PRs. Add a new `backend/personas/{cohort_id}.json` file following the schema above.
