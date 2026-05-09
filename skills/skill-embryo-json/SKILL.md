# Check Content-Encoding before parsing JSON body

> Status: evolved
> Version: 0.1.0
> Risk: medium
> Node: 45657726-a0db-4a11-8a33-ff1989197bc4

## Triggers
- Content-Encoding JSON parse failure
- compressed JSON request body
- garbled request bytes before JSON.parse
- gzip/br/deflate body decoding

## Preconditions
- request body is expected to be JSON
- raw request bytes look garbled or JSON.parse fails
- Content-Encoding may be present, absent, duplicated, or altered by proxy/middleware

## Procedure
1. Default path for garbled bytes or JSON.parse failure: inspect Content-Encoding first, before schema, charset, or JSON structure guesses.
2. If Content-Encoding is gzip, br, or deflate, decompress the raw bytes before converting to text or calling JSON.parse.
3. Use the matching byte decoder: gzip -> gunzip, br -> Brotli decompression, deflate -> zlib inflate; if deflate interoperability is uncertain, try raw deflate as fallback.
4. After decompression, decode bytes as UTF-8 or the declared charset, then call JSON.parse.
5. If multiple Content-Encoding values are present, decode them in reverse order of application, then charset-decode and parse JSON.
6. Only enter the transfer-framing branch when Transfer-Encoding: chunked, partial chunks, or body boundary issues are visible; then ensure dechunking and full buffering before content decompression.
7. Only enter the completeness branch when Content-Length mismatch, truncated compressed stream, or premature socket close is suspected; verify received byte count before decompression.
8. If Content-Encoding is missing but bytes are non-textual, check compression clues such as gzip magic bytes 1f 8b, and investigate proxies that stripped headers, already decompressed, or double-compressed the body.
9. Keep the final diagnostic order explicit: Content-Encoding/decompression first for ordinary garbled JSON; advanced framing/completeness/proxy checks only when their cues exist.
10. Also confirm Content-Type is application/json and the payload is not encrypted or unrelated binary data.

## Verification
For ordinary garbled JSON, name Content-Encoding first and decompress before JSON.parse. For multi-encoding/proxy/framing cases, branch into reverse-order decoding, dechunking, completeness, and proxy-header diagnostics only when those cues are present.

## Failure Modes
- Putting Transfer-Encoding or body completeness before Content-Encoding in ordinary garbled JSON cases.
- Assuming body is plain JSON without checking Content-Encoding.
- Handling gzip but ignoring br or deflate.
- Decoding multiple Content-Encoding values in the wrong order.
- Ignoring raw deflate vs zlib-wrapped deflate compatibility differences.
- Converting compressed bytes to UTF-8 string before decompression.
- Running JSON.parse before decompression.
- Overloading simple gzip cases with irrelevant advanced diagnostics.
- Missing a proxy that stripped Content-Encoding, already decompressed, or double-compressed the body when headers and bytes disagree.

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
  "m3_version": "v7.0-M3",
  "mutation_reason": "Real Darwin eval lost to baseline because skill focused too narrowly on gzip and omitted br/deflate, decompression ordering, charset, body parser ordering, and header stripping checks.",
  "mutation_round": 3,
  "mutation_reason_round_2": "Real Darwin round 2 lost the br/deflate prompt because baseline covered transfer framing/dechunking, multi Content-Encoding reverse order, raw deflate vs zlib wrapper, body completeness, and magic bytes. Add those diagnostics explicitly.",
  "mutation_reason_round_3": "Round 2 overgeneralized. Round 3 uses scenario branching: simple garbled JSON -> Content-Encoding first; advanced framing/completeness/proxy branches only when cues exist.",
  "trigger_refinement_reason": "Round 3 Darwin passed 4/4, but Mnemosyne trigger_precision was 0 because trigger list was too broad. Refine to high-precision triggers rather than lowering threshold."
}
```
