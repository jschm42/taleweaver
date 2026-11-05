export interface ScriptSnippet {
  label: string
  code: string
}

const COMMON_SNIPPETS: ScriptSnippet[] = [
  {
    label: 'GM Narration (Game Master)',
    code: 'tw.story.narrate("You take the piece of chocolate. Maybe it will help with the persuasion.")\n',
  },
  {
    label: 'System Notification',
    code: 'tw.system("System notification message.")\n',
  },
  {
    label: 'Save game (checkpoint)',
    code: 'tw.save("Before the duel")\n',
  },
  {
    label: 'Modify player stat',
    code: 'hp = tw.player.get_stat("hp", 100)\ntw.player.set_stat("hp", max(0, hp - 10))\n',
  },
  {
    label: 'Add item to inventory',
    code: 'tw.player.add_item("IRON_KEY")\n',
  },
  {
    label: 'Scene attribute',
    code: 'tw.scene.set_attribute("is_visited", True)\n',
  },
  {
    label: 'NPC speech',
    code: 'tw.npcs.say("NPC_ID", "Greetings, traveler!")\n',
  },
  {
    label: 'Move NPC to scene',
    code: 'tw.npcs.move("NPC_ID", "current")\n',
  },
  {
    label: 'Transfer item (NPC)',
    code: '# NPC hands an item it carries to the player:\ntw.npcs.give_to_player("NPC_ID", "ITEM_ID")\n# Or drop from NPC into scene:\n# tw.npcs.drop_item("NPC_ID", "ITEM_ID")\n# Or give item to NPC:\n# tw.npcs.give_item("NPC_ID", "ITEM_ID")\n',
  },
  {
    label: 'Clone item (dispenser)',
    code: '# Copies a (hidden) template item and hands the copy to the player:\npotion = tw.objects.get("HEALING_POTION").clone()\nif potion:\n    potion.reveal()\n    potion.move_to("player")\n',
  },
  {
    label: 'Container contents',
    code: '# List, put into and take out of a container:\nids = tw.objects.get("CHEST_ID").item_ids\ntw.objects.put_in_container("ITEM_ID", "CHEST_ID")\n# tw.objects.take_from_container("CHEST_ID", "ITEM_ID", to="player")\n',
  },
  {
    label: 'Destroy / hide item',
    code: 'tw.objects.destroy("ITEM_ID")\n# Or keep it, but out of sight:\n# tw.objects.hide("ITEM_ID")\n# tw.objects.reveal("ITEM_ID")\n',
  },
  {
    label: 'NPC speaks (GM-worded)',
    code: '# The GM writes the line in the next narration, in character:\ntw.npcs.say_directed("NPC_ID", "sings an old sailor song")\n# Fixed wording instead:\n# tw.npcs.say("NPC_ID", "Ahoy!")\n',
  },
  {
    label: 'Change NPC personality',
    code: '# Changes how the GM plays the NPC for the rest of this game:\ntw.npcs.set_character("NPC_ID", "Hostile and suspicious; short, rude answers.")\n# Or add / remove a single trait:\n# tw.npcs.add_trait("NPC_ID", "drunk")\n# tw.npcs.remove_trait("NPC_ID", "drunk")\n',
  },
  {
    label: 'Change NPC combat allies',
    code: '# NPCs in the same combat group fight together (applies from the next fight on):\ntw.npcs.set_combat_group("NPC_ID", "GUARDS")\n# Turn an NPC into a bystander who only fights when attacked directly:\n# tw.npcs.set_assist_mode("NPC_ID", "NEVER")\n',
  },
  {
    label: 'Spawn NPC pack (clone)',
    code: '# Spawns fresh copies of a (hidden) template NPC; clones share its combat group:\nfor i in range(5):\n    tw.npcs.clone("NPC_ID", scene_id="current", hidden=False)\n',
  },
  {
    label: 'Defeat / Kill NPC',
    code: 'tw.npcs.kill("NPC_ID", drop_inventory=True)\n',
  },
  {
    label: 'Choice dialog',
    code: '# Opens a choice dialog. The handler must be defined in the global init script:\n#   def on_wire_choice(answ):\n#       if answ == 0:\n#           tw.vars.set("bomb_disarmed", True)\ntw.dialog.choose("The bomb starts ticking. What do you do?", ["Cut the red wire", "Cut the blue wire", "Run"], on_choice="on_wire_choice")\n',
  },
]

const SWITCH_CONTEXTS = ['switch_success', 'switch_failure', 'transition_success', 'transition_failure']

/** Context-specific snippets, listed before the common ones. */
const CONTEXT_SNIPPETS: Record<string, ScriptSnippet[]> = {
  init_script: [
    {
      label: 'Choice dialog handler',
      code: '# Called with the index of the chosen option (its position in the options list).\ndef on_wire_choice(answ):\n    if answ == 0:\n        tw.vars.set("bomb_disarmed", True)\n        tw.narrate("The ticking stops.")\n        return\n    tw.game.game_over("The bomb exploded.")\n',
    },
    {
      label: 'Dialogue tree',
      code: '# Start it from any script: tw.dialog.tree(SMITH_TALK, on_end="on_smith_end", on_action="on_smith_action")\nSMITH_TALK = {\n    "npc_id": "SMITH",\n    "initial_node": "root",\n    "nodes": {\n        "root": {\n            "npc_text": "What do you want?",\n            "responses": [\n                {"text": "A sword. [50 Gold]", "condition": "tw.vars.get(\'gold\', 0) >= 50", "action": "BUY_SWORD", "next_node": "root"},\n                {"text": "Any rumours?", "once": True, "script": "tw.vars.set(\'heard_rumour\', True)", "next_node": "root"},\n                {"text": "Bye.", "next_node": None},\n            ],\n        },\n    },\n}\n\ndef on_smith_action(action, choice):\n    if action == "BUY_SWORD":\n        tw.vars.set("gold", tw.vars.get("gold", 0) - 50)\n        tw.player.take_item("SWORD")\n\ndef on_smith_end(path):\n    tw.vars.set("smith_talked", True)\n',
    },
    {
      label: 'Shared helper function',
      code: 'def has_all(*item_ids):\n    return all(tw.player.has_item(i) for i in item_ids)\n',
    },
  ],
  on_pickup: [
    {
      label: 'Pickup curse / buff',
      code: 'tw.player.set_stat("strength", tw.player.get_stat("strength", 10) + 2)\ntw.narrate("You feel surging power coursing through your veins.")\n',
    },
  ],
  soft_rule: [
    {
      label: 'NPC hands player an item',
      code: 'item = tw.npcs.give_to_player("NPC_ID", "ITEM_ID")\nif item:\n    tw.npcs.say("NPC_ID", "Here, take it.")\n',
    },
    {
      label: 'Change NPC trust',
      code: 'tw.vars.set("NPC_TRUST", tw.vars.get("NPC_TRUST", 0) - 1)\n',
    },
  ],
  on_receive_item: [
    {
      label: 'Accept the right item, return the rest',
      code: "if 'SILVER_RING' in received_item_ids:\n    tw.vars.set('ring_returned', True)\n    tw.story.direct('The NPC is deeply moved and thanks the player warmly.')\nelse:\n    for item_id in received_item_ids:\n        tw.npcs.give_to_player('NPC_ID', item_id)\n    tw.story.direct('The NPC politely hands the gift back.')\n",
    },
  ],
  on_defeat: [
    {
      label: 'Spawn reward on defeat',
      code: 'tw.player.add_item("ANCIENT_AMULET")\ntw.narrate("The foe drops a glowing amulet upon falling.")\n',
    },
  ],
  special_action: [
    {
      label: 'React to a critical success',
      code: "if special['crit']:\n    tw.story.narrate('A devastating blow!')\n",
    },
    {
      label: 'Remember who used the special',
      code: "tw.vars.set('last_special_caster', special['caster'])\n",
    },
    {
      label: 'Backfire on failure',
      code: "if not special['success']:\n    tw.player.damage(5)\n    tw.story.narrate('The spell backfires! (-5 HP)')\n",
    },
  ],
  on_enter_scene: [
    {
      label: 'First entrance trigger',
      code: 'if not tw.scene.get_attribute("visited", False):\n    tw.scene.set_attribute("visited", True)\n    tw.narrate("You step into the chamber for the first time.")\n',
    },
  ],
  switch: [
    {
      label: 'Flip / change another switch',
      code: 'tw.switches.set_state("OTHER_SWITCH", "ON")\ntw.story.narrate("You hear heavy machinery hum to life in the distance.")\n',
    },
    {
      label: 'Inspect switch state',
      code: 'if tw.switches.get_state("LEVER_ID") == "ACTIVE":\n    tw.vars.set("puzzle_solved", True)\n    tw.story.narrate("The final seal is broken!")\n',
    },
  ],
}

/** Guard expressions are single expressions, so the statement-style common snippets do not apply. */
const GUARD_SNIPPETS: ScriptSnippet[] = [
  {
    label: 'Check quest / script flag',
    code: "tw.vars.get('puzzle_solved', False) == True",
  },
  {
    label: 'Check switch state',
    code: "tw.switches.get('SWITCH_ID') == 'ON'",
  },
  {
    label: 'Check player inventory item',
    code: "tw.player.has_item('KEY_ID')",
  },
  {
    label: 'Combined guard (AND / OR)',
    code: "tw.vars.get('flag_a', False) and tw.switches.get('LEVER') == 'ACTIVE'",
  },
  {
    label: 'Check player stat threshold',
    code: "tw.player.get_stat('hp', 100) > 50",
  },
]

const CONTEXT_ALIASES: Record<string, string> = {
  on_drop: 'on_pickup',
  on_protagonist_enters_scene: 'on_enter_scene',
  ...Object.fromEntries(SWITCH_CONTEXTS.map(ctx => [ctx, 'switch'])),
}

/** Snippet templates offered by the script editor for a given trigger context. */
export function snippetsForContext(context: string): ScriptSnippet[] {
  if (context === 'guard_expression') return GUARD_SNIPPETS
  const specific = CONTEXT_SNIPPETS[CONTEXT_ALIASES[context] ?? context] ?? []
  return [...specific, ...COMMON_SNIPPETS]
}
