# Windows SQLite Encoding Check

> Status: approved
> Version: 0.1.0
> Risk: low
> Node: 6276392d-3297-4698-8480-c8ab9ec9b87d

## Triggers
- SQLite Chinese mojibake
- PowerShell mojibake

## Preconditions
- PowerShell or terminal displays Chinese text incorrectly
- SQLite content may be mistaken for corrupted data

## Procedure
1. Verify stored codepoints with unicode_escape before repairing data
2. Distinguish console display mojibake from actual data corruption

## Verification
预检快照 encodes as \u9884\u68c0\u5feb\u7167

## Failure Modes
- PowerShell console display may be mojibake even when DB data is correct

## Evidence
### Source Nodes
- df79f577-82f9-4bac-bc59-c7b7d2c185d2

### Verification Nodes
- 0201339f-7dc7-4e3b-be99-db85cb0dea8e
- bc2dffdc-c346-41ee-8228-edf1cf3b7d13

## Metadata
```json
{
  "imported_from": "v7_demo"
}
```
