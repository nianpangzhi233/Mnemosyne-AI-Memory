# Check Content-Encoding before parsing JSON body

> Status: evolved
> Version: 0.1.0
> Risk: medium
> Node: 45657726-a0db-4a11-8a33-ff1989197bc4

## Triggers
- api_proxy
- testing
- JSON parsing
- gzip body

## Preconditions
- request body is expected to be JSON
- Content-Encoding header may be present

## Procedure
1. Read the Content-Encoding header from the request.
2. If Content-Encoding includes 'gzip', decompress the body using gzip before parsing JSON.
3. If no Content-Encoding or it is not gzip, parse the body as plain JSON.

## Verification
After applying the procedure, the JSON parser should not produce garbled output or errors.

## Failure Modes
- Assuming body is always plain JSON without checking headers
- Not handling other encodings like deflate or br

## Evidence
### Source Nodes
- 8344a5fc-ffbd-4120-a363-d13761567e8a
- b28d3c70-b4e6-4741-853b-20bcada6464e
- ba477b3d-a3b7-412c-a530-11a978dcb59d

### Verification Nodes
- 8344a5fc-ffbd-4120-a363-d13761567e8a
- b28d3c70-b4e6-4741-853b-20bcada6464e
- ba477b3d-a3b7-412c-a530-11a978dcb59d

## Metadata
```json
{
  "discovered_by": "SkillEmbryoPhase",
  "cluster_reason": "connected component of strong similar_to experience edges",
  "cluster_size": 3,
  "cluster_edge_count": 2,
  "average_edge_weight": 0.859,
  "m2_version": "v7.0-M2",
  "developed_by": "SkillDevelopmentPhase",
  "development_model": "deepseek-v4-flash",
  "development_rationale": "Multiple source memories confirm that failing to check Content-Encoding before JSON parsing causes garbled data, and the fix is to decompress gzip first.",
  "m3_version": "v7.0-M3"
}
```
