---
name: "Reorganize File"
description: "Refactor and reorganize a file that has become too large or confusing, applying best practices."
argument-hint: "Any specific focus or rules for this refactoring?"
---

Please analyze the provided file (or selected code) which has grown too large or confusing. 
Your task is to refactor and reorganize it following clean code best practices.

### Objectives:
1. **Modularity:** Break down large classes, components, or functions into smaller, single-responsibility pieces.
2. **Readability:** Improve naming conventions, reduce deep nesting, and clarify complex logic.
3. **Structure:** Group related functionality together. If the file is doing too many things, suggest how to split it into multiple modules/files.
4. **Maintainability:** Ensure the new structure is easy to test and extend in the future.

### Instructions:
- First, provide a brief summary of the main issues in the current code and your proposed plan to refactor them.
- Then, perform the refactoring. 
- If splitting into multiple files is the best approach, generate the code for each new file and explain the new architecture.