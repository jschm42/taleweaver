---
name: taleweaver-adventure-creator
description: Generates structured adventure concepts for TaleWeaver using Sequence, Scene, NPC, and Item tags.
---

# TaleWeaver Adventure Creator

Use this skill when you need to generate, brainstorm, or refine an adventure concept for the TaleWeaver platform. 

TaleWeaver adventures require a very specific structured syntax to guide the AI generation effectively. You must use this syntax when writing the "Story Idea & Context" for a new adventure.

## The Syntax

You must use linear sequences and specific entity tags to outline the story chronologically.

1.  **Sequences (`[Sequence: X]`)**: The adventure must be broken down into chronological chapters, numbered sequentially. Maximum 15 sequences.
2.  **Scenes (`[Scene: X]`)**: Specific locations within a sequence.
3.  **NPCs (`[NPC: X]`)**: Characters the player interacts with.
4.  **Items (`[Item: X]`)**: Important objects the player acquires or uses.

## Example Format

When generating an adventure concept, format your output strictly using these tags so the user can copy-paste it directly into the World-Builder:

```text
[Sequence: 1] The Prison Escape
The player starts in a damp cell and must find a way to pick the lock. 

[Scene: 1] Damp Cell
A dark, moldy cell with a rusted iron door. Water drips from the ceiling.

[NPC: 1] Old Man
A crazy prisoner in the neighboring cell who gives the player a rusty shiv.

[Item: 1] Rusty Shiv
A crude weapon made from a piece of scrap metal.

[Sequence: 2] The Sewers
After escaping the cell, the player navigates the maze-like sewers below the prison. 
They must defeat a giant rat to reach the exit.

[Scene: 2] Sewer Tunnels
A labyrinth of waist-deep water and crumbling brickwork.
```

## Guidelines for Adventure Generation

- **Directly Usable:** Provide the structured text in a code block so it can be easily copied by the user.
- **Be Specific:** The more descriptive the entities and sequences, the better the final game generation will be.
- **Maintain Continuity:** Ensure that items found in one sequence are logically used or referenced later.
- **Keep it Chronological:** Sequences must flow linearly from 1 to N.
- **Builder Mode Suggestion:** Always conclude your output by recommending whether the user should use "Strict Adherence" (if the structure is critical and must be followed exactly) or "Creative Expansion" (if the AI should fill in gaps and add intermediate steps).
