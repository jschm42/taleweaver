# World-Builder Syntax Guide

TaleWeaver's World-Builder supports a structured prompting syntax. By incorporating specific tags into your **Story Idea & Context**, you can deterministically guide the AI when generating your adventure's content.

## Linear Sequences

The most powerful feature of the structured syntax is the ability to outline a linear storyline using `[Sequence: X]` tags. The AI will segment your adventure into distinct, chronological chapters.

> **Important:** The maximum number of sequences per adventure is strictly capped at **15**.

### Basic Usage

Define a sequence by writing `[Sequence: <number>]` followed by its title and a description.

```text
[Sequence: 1] The Prison Escape
The player starts in a damp cell and must find a way to pick the lock. 
They meet an old man who gives them a rusty shiv.

[Sequence: 2] The Sewers
After escaping the cell, the player navigates the maze-like sewers below the prison. 
They must defeat a giant rat to reach the exit.
```

### Builder Modes

When using Sequence tags, you must choose a Builder Mode in the generator:

1. **Strict Adherence:** The AI will generate exactly the sequences you provided and map them directly into the game's state machine. The player must complete them in order.
2. **Creative Expansion:** The AI uses your sequences as a foundation but is free to add intermediate steps, split sequences, or inject new ideas to flesh out the world.

## Entity Tags

In addition to sequences, you can force the generation of specific entities by using tags like `[Scene: X]`, `[NPC: X]`, and `[Item: X]`.

### Basic Usage

You can define these entity tags alongside your sequences to dictate specific locations, characters, or items the AI must generate and integrate into the story:

```text
[Sequence: 1] The Prison Escape
The player starts in a damp cell and must find a way to pick the lock. 

[Scene: 1] Damp Cell
A dark, moldy cell with a rusted iron door. Water drips from the ceiling.

[NPC: 1] Old Man
A crazy prisoner in the neighboring cell who gives the player a rusty shiv.

[Item: 1] Rusty Shiv
A crude weapon made from a piece of scrap metal.
```
