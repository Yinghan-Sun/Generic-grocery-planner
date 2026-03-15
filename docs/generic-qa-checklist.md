# Generic Planner QA Checklist

Use this checklist for manual regression testing of the generic grocery planner demo.

## Setup

Build the frontend bundle:

```bash
cd dietdashboard/frontend && ./bundle.sh
```

Make sure the local runtime artifacts exist:
- `data/data.db`
- `data/store_discovery.db`

Start the app:

```bash
uv run python -m dietdashboard.app
```

## Fast Automated Checks

```bash
make test-generic
make qa-generic
```

## Manual Checklist

### Page Load

- Open `/`.
- Confirm the generic planner loads.
- Confirm there is no legacy navigation.

### Address Search / Coordinates

- Enter `Mountain View, CA` and click `Find Nearby Supermarkets`.
- Confirm nearby stores render.
- Confirm advanced `lat` and `lon` fields are populated when geocoding succeeds.
- Confirm the page also works when coordinates are entered directly.

### Nearby Stores

- Confirm stores render with:
  - name
  - category
  - distance
- Confirm obvious duplicates are removed.
- Confirm the no-store case is handled cleanly.

### Dietary Preferences

- Toggle `Vegetarian` and confirm meat/fish items disappear.
- Toggle `Vegan` and confirm animal-derived foods disappear.
- Toggle `Dairy-free` and confirm dairy items disappear.
- Toggle `Low prep` and confirm the basket becomes more convenience-oriented.

### Goal Presets

- Compare:
  - muscle gain
  - fat loss
  - maintenance
  - budget-friendly healthy
- Confirm the main basket foods change, not just the quantities.

### Meal Style

- Set `Breakfast` and confirm the basket looks breakfast-oriented.
- Set `Snack` and confirm the basket becomes more portable / low-prep.
- Set `Lunch / dinner` and confirm the basket becomes more meal-base oriented.

### Multi-Day + Shopping Mode

- Compare `1 day` vs `3 days` vs `7 days`.
- Confirm quantities scale with the shopping window.
- Compare `Fresh` vs `Balanced` vs `Bulk`.
- Confirm perishables and pantry-friendly items shift appropriately.

### Pantry Items

- Check a few pantry items such as:
  - `Rice`
  - `Broccoli`
  - `Eggs`
- Rebuild the list.
- Confirm those items are reduced or removed where practical.
- Confirm nutrition totals still reflect the intended plan.

### Basket Cost + Price Messaging

- Confirm typical basket cost appears when foods are priced.
- Confirm price wording stays representative and regional, not exact.
- Confirm USDA/BLS source messaging is visible in pricing notes.

### Store Picks

- Confirm grouped store picks appear when nearby stores exist:
  - one-stop pick
  - budget pick
  - produce pick
  - bulk pick
- Confirm the ranked store-fit section still appears.

### Meal Suggestions

- Confirm breakfast suggestions look breakfast-appropriate.
- Confirm snack suggestions are compact and portable.
- Confirm later suggestions reuse fewer of the same items.

### Export / Share

- Click `Copy shopping list`.
- Click `Copy full plan`.
- Click `Download as text`.
- Confirm each action succeeds and the exported text stays readable.

## Useful Commands

Catalog audit:

```bash
make check-generic-catalog
```

Price coverage audit:

```bash
make check-generic-price-coverage
```

Store index summary:

```bash
make store-discovery-summary
```

Optional local store maintenance:

```bash
make backfill-generic-stores
make ingest-foursquare-stores
```
