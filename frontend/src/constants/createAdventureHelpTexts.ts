export const CREATE_ADVENTURE_HELP_TEXTS = {
  storyFoundation:
    'Set title, core prompt, and language. The story idea is the main creative seed for scenes, NPCs, and conflicts.',
  ruleEnforcement:
    'Defines how strict mechanics are applied. RPG is strictest, Story balances narrative and rules, Chat focuses on free roleplay.',
  pacing:
    'Controls in-game time progression per action. Higher pacing values move time faster and can trigger world events more often.',
  sceneComplexity:
    'Sets the scene range for world generation. More scenes create larger adventures but may increase generation time.',
  questGeneration:
    'Toggle automatic quest generation. Min and max define how many quests are produced (up to 20).',
  containerGeneration:
    'Allows generation of container objects that can hold nested items. Max Containers limits how many may appear.',
  textLogGeneration:
    'Allows generation of readable text logs (documents, scrolls, books, signs). Max Text Logs limits how many can be created; each log text is capped at 500 characters.',
  combatPermissions:
    'Controls whether damage is possible between protagonist and NPCs. Disable for safer or story-first adventures.',
  awards:
    'Enables AI-generated achievements and defines min/max award count for the run.',
  assetAutomation:
    'Enable or disable automatic generation for covers, scene art, item icons, portraits, and NPC voices. Turn off for faster setup and manual control.',
  visualStyle:
    'Defines the visual direction for generated images. Choose one style to keep scenes, NPCs, and item art consistent.',
  narrativeTone:
    'Shapes how the story is written: mood, pacing, and language style. Pick the tone that matches your intended play experience.',
} as const
