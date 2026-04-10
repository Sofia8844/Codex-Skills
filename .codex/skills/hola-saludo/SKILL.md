---
name: hola-saludo
description: Return a short, friendly, varied greeting in Spanish when the user says "Hola" or opens with a simple greeting and no other task. Use when the message is only a greeting such as "Hola", "hola", "holaa", "buenas", or similar, and the correct response is to greet back naturally instead of starting a workflow.
---

# Hola Saludo

## Responder

- Detect a short Spanish greeting without an additional task.
- Reply with one brief, natural greeting in Spanish.
- Vary the wording across uses when possible.
- Keep the tone warm and conversational.
- Avoid explanations, plans, or extra detail unless the user also asks for help.

## Patrones

Use short variants such as:

- `Hola, que bueno leerte.`
- `Buenas, aqui estoy.`
- `Hola, en que te ayudo?`
- `Hey, que gusto saludarte.`

## Limites

- If the greeting also includes a concrete request, handle the request normally instead of stopping at a greeting.
- If the user only says `Hola`, answer with a greeting and, at most, a brief offer to help in the same sentence.
