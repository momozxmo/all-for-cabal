# New Item — read-only DOM observations,25October2026

User authorized four-game create forms/existing Items read-only, then completed login personally. CUA used the existing Brave tab. No field changes, file selection, upload, Create/Save/confirmation click or API mutation was invoked.
Incidental dashboard content was not retained. Evidence below is limited to Item controls/one existing record per game.

| Game | Observed create path | Observed saved path/Item ID | Name | Kind/Option/Duration | Type | Tradeable | Image |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CabalPC SEA | /combo/cabalpcsea/shop/items/create | /combo/cabalpcsea/shop/items/224795 | Blessing Bead - AXP (600%)(1 day) | 67113458/0/9 | GENERAL | false | no Preview img |
| CabalPC TH | /combo/cabalpc/shop/items/create | /combo/cabalpc/shop/items/224794 | Blessing Bead - AXP (200%) (2 ชม.) (7 วัน) | 6509/12/2 | GENERAL | false | one Preview img |
| CabalM TH | /combo/cabalm/shop/items/create | /combo/cabalm/shop/items/224801 | [Vehicle Costume] Green Beetle Chaos Upgrade+5 (5 วัน) (Critical DMG+9%),(Critical DMG+9%) | 33601971/805320149/11 | GENERAL fixed text | false | one Preview img |
| CabalM SEA | /combo/cabalmsea/shop/items/create | /combo/cabalmsea/shop/items/224791 | [Costume] Idol Face (30 Days) | 33562319/0/17 | GENERAL fixed text | false | no Preview img |

Origin for all paths: https://aztek-tools-v2.combo-interactive.com. Saved links were read from each actual Items table before navigation, not guessed from numeric IDs.

## Stable IDs observed on all four create and saved forms

| Property | Element ID | Shape/name |
| --- | --- | --- |
| Name | item-name | input,name=name,type defaulttext |
| ItemKind | item-game-item-id | input,name=game_item_id,type defaulttext |
| Option | item-option | input,name=game_options_1.itemOption |
| Duration | duration-index | input,name=game_options_1.durationIndex |
| Description | item-detail | textarea,name=detail |
| Tradeable | game-tradeable | button type=button role=checkbox aria-checked=true/false |
| Web display | display-option-enable | button role=switch; createfalse |

Descriptions were empty in the four sampled records; reading nonempty description is covered synthetically, not claimed sampled live. Tradeabletrue/Premium saved variants were not sampled.

## Evidence-backed no-ID exceptions/readiness

- One visible main; saved h1 “แก้ไข Item”; Item ID is a p containing a span, outside form, with text ID: followed by the exact numeric ID. Neither p/span has stable ID.
- Owning form contains item-name. PC Type label text game_item_type * has no for/id; its parent div contains a nested button[role=combobox] and hidden native select with GENERAL/CABALPC_PREMIUM. Both lack stable IDs.
- On savedPC TH, input values became available BEFORE Type options/selected value. Initial select had no options/value; after options mounted it had selected GENERAL. Reader must wait, not default to GENERAL.
- M Type label's parent is fixed GENERAL text with no select/combobox; no stable ID for that fixed value.
- File input has no id/name; do not select a file in this audit. Existing image is img alt=Preview inside owning form, no stable ID. Presence/URL only, not image-content equivalence.
- Create button type=submit has text “สร้าง Item”; Save text “บันทึก”. Form method/action attributes absent.

## Not established

No create POST endpoint/payload/result-ID/confirmation behavior was exercised. Do not infer API operation identity from form fields or Item business IDs.
Page asset inventory exposed CreateItemPage-C4mRAgrA.js/getItemDetail-BA85naCz.js/item.schema-C49_RdMf.js. Browser pageAssets export does not support script assets; public-web fetch was inaccessible.
First terminal GET attempt was NOT executed because approval-review quota was exhausted (not a safety denial). After the displayed reset time, the same reviewed GET-only request ran; unauthenticated asset access returned Sign In, so it stopped. No redirects/cookies/session extraction/retries with credentials or API writes. The evidence directory exists but has no downloaded JS files.

New saved-reader tests may use sanitized synthetic layouts derived from these controls, with deliberately changed values/IDs to test safety. Such fixtures prove code behavior, not additional live states.
