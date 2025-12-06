# OpenAI Structured Outputs - JSON Schema Requirements

Reference: https://platform.openai.com/docs/guides/structured-outputs
Reference: https://cookbook.openai.com/examples/structured_outputs_intro

## Overview

OpenAI Structured Outputs allows the API to generate JSON that strictly adheres to a provided JSON schema. When `strict: true` is set, the model will always generate responses that match the schema exactly.

## Schema Requirements for Strict Mode

### 1. `additionalProperties: false` (REQUIRED)

Every object in the schema MUST have `additionalProperties: false`. This applies to:
- The root schema object
- All nested objects
- All objects inside array `items`

```json
{
  "type": "object",
  "properties": { ... },
  "required": [...],
  "additionalProperties": false  // REQUIRED
}
```

### 2. All Properties Must Be Required

Every property defined in `properties` must also be listed in the `required` array. OpenAI does not support optional properties in strict mode.

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "age": { "type": "integer" }
  },
  "required": ["name", "age"],  // Must include ALL properties
  "additionalProperties": false
}
```

### 3. No `$ref` References (Must Be Dereferenced)

OpenAI's API does NOT properly resolve `$ref` pointers. Pydantic generates schemas with `$defs` and `$ref`, which must be dereferenced (inlined) before sending to OpenAI.

**Pydantic output (not directly usable):**
```json
{
  "$defs": { "Item": { ... } },
  "properties": {
    "items": { "items": { "$ref": "#/$defs/Item" } }
  }
}
```

**Required format (dereferenced):**
```json
{
  "properties": {
    "items": {
      "items": {
        "type": "object",
        "properties": { ... },
        "required": [...],
        "additionalProperties": false
      }
    }
  }
}
```

### 4. Supported Types

- `string` - With optional `maxLength`, `minLength`, `pattern`, `enum`
- `integer` - With optional `minimum`, `maximum`
- `number` - With optional `minimum`, `maximum`
- `boolean`
- `array` - With `items` schema, optional `minItems`, `maxItems`
- `object` - With `properties`, `required`, `additionalProperties: false`
- `null` - For nullable fields (use `"type": ["string", "null"]`)
- `enum` - Predefined set of values

### 5. Unsupported Features

- `$ref` and `$defs` (must be dereferenced)
- `anyOf`, `oneOf`, `allOf` (limited support)
- `if/then/else` conditionals
- `patternProperties`
- `unevaluatedProperties`
- `dependencies`
- `default` values (ignored by API)
- Dynamic schemas

### 6. Depth and Size Limits

- Maximum schema depth: ~5 levels of nesting
- Maximum total properties: ~100 across the entire schema
- Large schemas may increase latency

## ACOG Implementation

### Pydantic Model Requirements

All Pydantic models used with OpenAI structured output must:

1. Include `model_config = ConfigDict(extra="forbid")` to generate `additionalProperties: false`
2. Make all fields required (no `default=...` or `Optional[...]`)
3. Use concrete types, not `dict[str, Any]`

```python
from pydantic import BaseModel, ConfigDict, Field

class VideoChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_seconds: int = Field(description="Timestamp in seconds")
    title: str = Field(description="Chapter title")
```

### Schema Dereferencing

The `OpenAIClient._dereference_schema()` method automatically:
1. Resolves all `$ref` pointers to their definitions
2. Inlines nested object schemas
3. Removes the `$defs` section

This happens automatically when using `complete_with_schema()`.

### Compliance Check

Run this to verify schema compliance:

```python
from acog.services.metadata import VideoMetadata
from acog.integrations.openai_client import OpenAIClient

client = OpenAIClient()
schema = VideoMetadata.model_json_schema()
dereferenced = client._dereference_schema(schema)

# Schema should have additionalProperties: false at all object levels
# All properties should be in required array
```

## Error Messages

Common OpenAI structured output errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `'additionalProperties' is required to be supplied and to be false` | Missing `additionalProperties: false` on nested object | Add `model_config = ConfigDict(extra="forbid")` to Pydantic model |
| `Invalid schema` with `$ref` | Schema contains unresolved references | Use `_dereference_schema()` before sending |
| `property X is not in required` | Property defined but not required | Add all properties to `required` array |

## Sources

- [OpenAI Cookbook - Structured Outputs Intro](https://cookbook.openai.com/examples/structured_outputs_intro)
- [OpenAI Python SDK - Helpers](https://github.com/openai/openai-python/blob/main/helpers.md)
- [JSON Schema - Object Properties](https://json-schema.org/understanding-json-schema/reference/object.html)
