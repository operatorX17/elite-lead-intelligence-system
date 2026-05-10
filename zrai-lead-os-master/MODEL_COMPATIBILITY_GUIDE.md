# Model Compatibility Guide - ZRAI Lead OS

## Problem: AI Model Infinite Loops & Tool Calling Issues

### Symptoms
- **Gemini 2.0 Flash Lite**: Infinite loop calling fake tools like `print(datetime.now())`
- **Claude 3 Haiku**: Generates fake Python code with simulated data instead of calling real backend
- **Small/Lite Models**: Don't properly support function calling in AI SDK format

### Root Cause
Smaller and "lite" versions of AI models lack the capability to properly understand and execute the function calling protocol used by the AI SDK. They either:
1. Hallucinate fake tool calls
2. Generate simulated responses instead of calling actual backend APIs
3. Get stuck in infinite loops

## Solution Implemented

### 1. Model Capability Tracking
Added `supportsTools` flag to each model in `frontend/lib/ai/models.ts`:

```typescript
{
  id: "google/gemini-2.0-flash-lite-001",
  name: "Gemini 2.0 Flash Lite",
  supportsTools: false, // ❌ Doesn't support function calling
}

{
  id: "anthropic/claude-3.5-sonnet",
  name: "Claude 3.5 Sonnet",
  supportsTools: true, // ✅ Fully supports function calling
}
```

### 2. Runtime Tool Disabling
Modified `frontend/app/(chat)/api/chat/route.ts` to:
- Check if selected model supports tools
- Disable tools for incapable models
- Log warnings to console
- Send user-facing warnings in the chat

### 3. User Guidance
Updated system prompts to inform users when tools are disabled and recommend capable models.

## Recommended Models for ZRAI Tools

### ✅ Fully Supported (Tool Calling Works)
- **Claude 3.5 Sonnet** - Best balance of speed and intelligence (RECOMMENDED)
- **GPT-4o** - Most capable OpenAI model
- **GPT-4o Mini** - Fast and cost-effective
- **Gemini 2.0 Flash** - Fast and capable (NOT the Lite version)
- **Gemini Pro 1.5** - Most capable Google model
- **Claude 3 Opus** - Most capable Anthropic model
- **Llama 3.1 70B** - Free, powerful open model
- **Mixtral 8x7B** - Powerful mixture of experts
- **DeepSeek Chat** - Affordable and capable

### ❌ Not Supported (Tools Disabled)
- **Gemini 2.0 Flash Lite** - Too small for function calling
- **Claude 3 Haiku** - Generates fake responses
- **Llama 3.2 3B** - Too small for function calling
- **Mistral 7B** - Too small for function calling

## Testing the Fix

### Before Fix
```bash
# User selects Gemini 2.0 Flash Lite
# User: "Find me 20 SaaS leads"
# Result: Infinite loop calling print(datetime.now())
```

### After Fix
```bash
# User selects Gemini 2.0 Flash Lite
# User: "Find me 20 SaaS leads"
# System: ⚠️ Warning displayed in chat
# AI: "The current model doesn't support ZRAI tools. Please switch to Claude 3.5 Sonnet..."
# Tools: Disabled (no infinite loop)
```

### Recommended Test
```bash
# 1. Start both services
cd frontend && pnpm dev  # Terminal 1
python run.py            # Terminal 2

# 2. Open http://localhost:3000
# 3. Select "Claude 3.5 Sonnet" from model dropdown
# 4. Ask: "Find me 20 SaaS leads in the US"
# 5. Verify: Tool is called, backend responds, leads displayed
```

## Architecture Flow

```
User Query → Frontend Chat
    ↓
Model Selection Check (NEW)
    ↓
Tools Enabled? → YES → Call Backend → LangGraph Agents → Supabase
    ↓
    NO → Warning Displayed → Regular Chat Response
```

## Helper Functions Added

### `modelSupportsTools(modelId: string): boolean`
Checks if a model supports tool calling.

### `getToolCapableModels(): ChatModel[]`
Returns list of all tool-capable models.

### `getBestToolModel(): string`
Returns the best available model for tool calling (prioritizes Claude 3.5 Sonnet).

## Configuration

No environment variables needed. The fix is automatic based on model selection.

## Troubleshooting

### Issue: Tools still not working with Claude 3.5 Sonnet
**Solution**: Check backend is running on port 8000:
```bash
curl http://localhost:8000/api/v1/metrics
```

### Issue: Warning appears for a model that should work
**Solution**: Update `supportsTools: true` in `frontend/lib/ai/models.ts`

### Issue: User wants to use Gemini Lite for non-tool tasks
**Solution**: This is fine! The model will work for regular chat, just without ZRAI tools.

## Future Improvements

1. **Dynamic Model Detection**: Query OpenRouter API for model capabilities
2. **Graceful Degradation**: Offer limited functionality for weak models
3. **Model Recommendations**: Suggest best model based on user's query type
4. **Cost Optimization**: Auto-select cheapest capable model for each task

## Related Files

- `frontend/lib/ai/models.ts` - Model definitions and capability flags
- `frontend/app/(chat)/api/chat/route.ts` - Tool enabling logic
- `frontend/lib/ai/prompts.ts` - User guidance prompts
- `frontend/lib/ai/providers.ts` - OpenRouter provider configuration
