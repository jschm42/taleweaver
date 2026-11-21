from typing import Any

DEFAULT_IMAGE_STYLES: list[dict[str, Any]] = [
    {
        "id": "dark-fantasy-painting",
        "name": "Dark Fantasy Painting",
        "description": "Moody oil painting with dramatic contrast and medieval grit.",
        "instruction": "dark fantasy oil painting, dramatic chiaroscuro, visible textured "
        "brushwork, deep shadows with warm firelight highlights, muted earthy "
        "palette with ember accents, weathered medieval materials, atmospheric haze",
        "image_url": "/assets/catalog/styles/dark-fantasy-painting_35657e9e.jpg",
    },
    {
        "id": "cinematic-realism",
        "name": "Cinematic Realism",
        "description": "Photorealistic film stills with motivated lighting and depth.",
        "instruction": "cinematic photorealism, film still look, widescreen framing, motivated "
        "natural and practical lighting, volumetric light, rich but natural color "
        "grade, shallow depth of field, realistic materials and skin texture, fine "
        "film grain",
        "image_url": "/assets/catalog/styles/cinematic-realism_bd485f41.jpg",
    },
    {
        "id": "stylized-rpg-art",
        "name": "Stylized RPG Art",
        "description": "Hand-painted game art with clean silhouettes and vivid, grounded colors.",
        "instruction": "stylized RPG concept art, hand-painted digital illustration, clean "
        "readable silhouettes, slightly exaggerated proportions, soft cel-like "
        "shading with painted textures, vibrant but grounded palette, clear focal "
        "point",
        "image_url": "/assets/catalog/styles/stylized-rpg-art_db5e95d6.jpg",
    },
    {
        "id": "grimdark-ink-sketch",
        "name": "Grimdark Ink Sketch",
        "description": "Raw pen-and-ink drawing with heavy washes and scratched textures.",
        "instruction": "grimdark pen and ink illustration, dense cross-hatching, scratchy "
        "expressive linework, heavy black ink washes, dry-brush and splatter "
        "texture, aged distressed paper, stark black and white, no color",
        "image_url": "/assets/catalog/styles/grimdark-ink-sketch_023b9ad4.jpg",
    },
    {
        "id": "cyberpunk-neon",
        "name": "Cyberpunk Neon",
        "description": "Neon-lit high tech with grime, haze and reflective surfaces.",
        "instruction": "cyberpunk aesthetic, high-tech low-life detail, saturated magenta and cyan "
        "neon light against deep shadow, reflective wet surfaces, holographic glow, "
        "haze, grime on chrome and plastic, futuristic noir mood",
        "image_url": "/assets/catalog/styles/cyberpunk-neon_e4b9fd38.jpg",
    },
    {
        "id": "ethereal-watercolor",
        "name": "Ethereal Watercolor",
        "description": "Soft, bleeding watercolor with a dreamlike, mystical light.",
        "instruction": "ethereal watercolor painting, wet-on-wet washes, soft bleeding edges, "
        "granulating pigment, white paper glowing through, gentle luminous light, "
        "dreamy pastel palette, delicate loose linework",
        "image_url": "/assets/catalog/styles/ethereal-watercolor_963ce2cd.jpg",
    },
    {
        "id": "science-fiction",
        "name": "Science-Fiction",
        "description": "Sleek, advanced technology rendered as clean concept art.",
        "instruction": "clean science fiction concept art, sleek hard-surface design, precise "
        "industrial detail, cool blue-white lighting with glowing interface "
        "accents, polished metal, glass and composite materials, cinematic wide "
        "composition",
        "image_url": "/assets/catalog/styles/science-fiction_93659096.jpg",
    },
    {
        "id": "pixelart",
        "name": "Pixelart",
        "description": "Classic 90s adventure game look with crisp pixels and a limited palette.",
        "instruction": "16-bit pixel art in the look of 1990s point-and-click adventure games, "
        "crisp visible pixels, limited color palette with dithering, hand-placed "
        "detail, no anti-aliasing, no blur, no text, no user interface",
        "image_url": "/assets/catalog/styles/pixelart_5fb230a4.jpg",
    },
    {
        "id": "film-noir",
        "name": "Film Noir",
        "description": "High-contrast black and white with hard shadows and smoky haze.",
        "instruction": "classic film noir, black and white 1940s cinematography, hard low-key "
        "lighting, deep shadows with bright edge highlights, strong chiaroscuro, "
        "slanted light patterns, smoky haze, grainy film texture, no color",
        "image_url": "/assets/catalog/styles/classic-film-noir_73cadd52.jpg",
    },
    {
        "id": "ghibli-whimsy",
        "name": "Ghibli-esque Whimsy",
        "description": "Hand-painted animation backgrounds with lush nature and nostalgic light.",
        "instruction": "hand-painted 2D animation background art, soft gouache and watercolor "
        "textures, gentle clean line art, lush detailed nature, warm nostalgic "
        "sunlight, soft rich palette, whimsical cozy atmosphere",
        "image_url": "/assets/catalog/styles/ghibli-esque-whimsy_37636857.jpg",
    },
    {
        "id": "retro-synthwave",
        "name": "Retro Synthwave",
        "description": "80s retro-futurism in glowing neon pink, violet and electric blue.",
        "instruction": "1980s synthwave retro-futurism, glowing neon pink, violet and electric "
        "blue palette, chrome highlights, sunset gradients, glowing wireframe "
        "accents, soft bloom, VHS scanline texture, airbrushed album-cover finish",
        "image_url": "/assets/catalog/styles/retro-synthwave_47522b15.jpg",
    },
    {
        "id": "bio-organic-gothic",
        "name": "Bio-Organic Gothic",
        "description": "Eerie fusion of biology and machinery in dark, skeletal detail.",
        "instruction": "bio-mechanical gothic art, organic and mechanical forms fused together, "
        "ribbed bone-like structures, cables like sinews, glossy wet surfaces and "
        "cold metal, near-monochrome black, bone and grey-green palette, low eerie "
        "light, intricate unsettling detail",
        "image_url": "/assets/catalog/styles/bio-organic-gothic_23707b39.jpg",
    },
    {
        "id": "impressionist-oil",
        "name": "Impressionist Oil",
        "description": "Expressive oil painting with thick impasto and shimmering light.",
        "instruction": "impressionist oil painting, thick impasto, visible broken brush and "
        "palette-knife strokes, dabs of pure color, shimmering natural light, soft "
        "edges, romantic atmosphere, visible canvas texture",
        "image_url": "/assets/catalog/styles/impressionist-oil_801143d7.jpg",
    },
    {
        "id": "shonen-anime",
        "name": "Modern Shonen Anime",
        "description": "Crisp line art, bold cel shading and high-energy lighting.",
        "instruction": "modern action anime key visual, crisp clean line art, bold cel shading "
        "with sharp shadow shapes, dynamic camera angle, dramatic rim light, "
        "saturated colors, energetic glowing effects, sharp focus",
        "image_url": "/assets/catalog/styles/modern-shonen-anime_7417820f.jpg",
    },
    {
        "id": "classical-comic",
        "name": "Classical Comic",
        "description": "Bold outlines, Ben-Day dots and vibrant primary colors of Silver Age "
        "comics.",
        "instruction": "Silver Age comic book art, bold black ink outlines, flat primary colors "
        "with Ben-Day halftone dots, dramatic spot blacks, dynamic composition, "
        "printed paper texture, no text, no speech bubbles, no captions",
        "image_url": "/assets/catalog/styles/classical-heroic-comic_8970c6ab.jpg",
    },
    {
        "id": "survival-science-fiction",
        "name": "Survival Science Fiction",
        "description": "Stranded on hostile worlds: worn, patched and improvised technology.",
        "instruction": "survival science fiction concept art, worn and improvised technology, "
        "scratched and patched hard-surface materials, dust, frost and grime, harsh "
        "alien light, desaturated palette with cold teal and warning-orange "
        "accents, haze, grounded realism, isolation and scarcity",
        "image_url": None,
    },
    {
        "id": "survival-rpg",
        "name": "Survival RPG",
        "description": "Gritty, readable game art of handmade gear and harsh wilderness.",
        "instruction": "survival RPG concept art, painterly game illustration, clear readable "
        "silhouettes, handcrafted and weathered materials like rope, hide, rough "
        "wood and rusted metal, earthy muted palette with warm firelight accents, "
        "natural overcast light, gritty but legible detail",
        "image_url": None,
    },
    {
        "id": "survival-realism",
        "name": "Survival Realism",
        "description": "Documentary photo look: real materials, natural light, no glamour.",
        "instruction": "photorealistic survival realism, documentary photography look, natural "
        "available light, overcast sky or low sun, 35mm lens, real materials with "
        "mud, wear and moisture, desaturated earthy color grade, fine film grain, "
        "no stylization, no magical glow",
        "image_url": None,
    },
    {
        "id": "storybook-gouache",
        "name": "Storybook Gouache",
        "description": "Warm, matte picture-book painting with gentle charm.",
        "instruction": "children's picture book illustration, opaque gouache painting, matte "
        "chalky texture, soft rounded shapes, warm limited palette, gentle diffused "
        "light, visible paper grain, charming and inviting",
        "image_url": None,
    },
    {
        "id": "ukiyo-e-woodblock",
        "name": "Ukiyo-e Woodblock",
        "description": "Flat colors and bold lines of Japanese woodblock prints.",
        "instruction": "ukiyo-e woodblock print, bold flowing outlines, flat areas of color, "
        "subtle bokashi gradients, stylized waves, clouds and wind lines, muted "
        "indigo, vermilion and ochre palette, washi paper texture, no text",
        "image_url": None,
    },
    {
        "id": "victorian-engraving",
        "name": "Victorian Engraving",
        "description": "Fine steel-engraving hatching of 19th-century books.",
        "instruction": "19th-century steel engraving illustration, fine parallel line hatching and "
        "cross-hatching, stippled shading, meticulous detail, monochrome ink on "
        "aged cream paper, encyclopedia plate look, no color",
        "image_url": None,
    },
    {
        "id": "art-nouveau",
        "name": "Art Nouveau",
        "description": "Ornamental frames, flowing lines and elegant natural forms.",
        "instruction": "Art Nouveau illustration, sinuous whiplash lines, ornamental floral "
        "borders, elegant stylized figures, flat decorative color areas with gold "
        "accents, muted sage, ochre and rose palette, poster lithograph texture, no "
        "text",
        "image_url": None,
    },
    {
        "id": "isometric-diorama",
        "name": "Isometric Diorama",
        "description": "A detailed miniature world seen from above at an angle.",
        "instruction": "isometric miniature diorama, three-quarter top-down view, tilt-shift depth "
        "of field, tiny highly detailed props, soft global illumination, clean "
        "readable layout, toy-like scale, cohesive palette",
        "image_url": None,
    },
    {
        "id": "low-poly-3d",
        "name": "Low-Poly 3D",
        "description": "Stylized game look with faceted shapes and clean light.",
        "instruction": "low-poly 3D render, flat-shaded faceted geometry, simple clean shapes, "
        "soft ambient occlusion, gentle directional light, harmonious pastel and "
        "earthy palette, stylized indie game look",
        "image_url": None,
    },
    {
        "id": "claymation",
        "name": "Claymation",
        "description": "Handmade stop-motion look with clay and fingerprints.",
        "instruction": "stop-motion claymation, handmade plasticine characters and sets, visible "
        "fingerprints and tool marks, slightly lumpy shapes, miniature practical "
        "lighting, shallow depth of field, playful saturated colors",
        "image_url": None,
    },
    {
        "id": "stained-glass",
        "name": "Stained Glass",
        "description": "Luminous colored glass framed by dark lead lines.",
        "instruction": "stained glass window art, jewel-toned translucent glass panels, bold dark "
        "lead lines, light glowing through the glass, simplified symbolic figures, "
        "Gothic window composition, rich ruby, sapphire and gold palette",
        "image_url": None,
    },
    {
        "id": "weird-west",
        "name": "Weird West",
        "description": "Dusty Frontier art with a supernatural edge.",
        "instruction": "weird west illustration, sun-bleached frontier landscapes, dust and heat "
        "haze, worn leather, wood and iron, low golden sun with long shadows, ochre "
        "and rust palette with eerie green accents, gritty painterly texture, "
        "uncanny undertone",
        "image_url": None,
    },
    {
        "id": "solarpunk",
        "name": "Solarpunk",
        "description": "Bright, green and hopeful future of nature and technology.",
        "instruction": "solarpunk concept art, lush greenery woven into elegant sustainable "
        "architecture, solar sails and glass, warm bright daylight, clean saturated "
        "greens, whites and gold, optimistic and airy atmosphere, art nouveau "
        "inspired curves",
        "image_url": None,
    },
]

DEFAULT_TONES: list[dict[str, Any]] = [
    {
        "id": "horror",
        "name": "Horror",
        "description": "Dread, uncertainty and escalating psychological pressure.",
        "instruction": "Build dread slowly: unsettling details, sparse comfort, threats that are "
        "heard before they are seen, and consequences that feel truly dangerous. "
        "Keep the unknown unexplained for as long as possible.",
        "image_url": "/assets/catalog/tones/horror_7e4a6db5.jpg",
    },
    {
        "id": "sci-fi",
        "name": "Sci-Fi",
        "description": "Futuristic systems, unknown technology and speculative mystery.",
        "instruction": "Ground the future in believable technology and its social consequences. "
        "Drive the story through discovery, technical puzzles and the question of "
        "what the new means for people.",
        "image_url": "/assets/catalog/tones/sci-fi_0b2e548f.jpg",
    },
    {
        "id": "sitcom",
        "name": "Sitcom",
        "description": "Comedic misunderstandings, playful pacing and memorable banter.",
        "instruction": "Favor witty dialogue, running gags, comic timing and low-stakes chaos. "
        "Setbacks are charming rather than cruel, and every scene ends on a beat "
        "that lands.",
        "image_url": "/assets/catalog/tones/sitcom_3b747e63.jpg",
    },
    {
        "id": "classic-rpg",
        "name": "Classic RPG",
        "description": "Heroic quests with balanced drama and wonder.",
        "instruction": "Keep a clear quest structure with meaningful choices, memorable allies and "
        "rivals, and a steady balance of danger, discovery and reward.",
        "image_url": "/assets/catalog/tones/classic-rpg_551efe58.jpg",
    },
    {
        "id": "heroic-epic",
        "name": "Heroic & Epic",
        "description": "Grand scale, legendary deeds and inspiring bravery.",
        "instruction": "Tell the story on a grand scale: ancient stakes, legendary places and "
        "deeds that will be sung about. Courage is costly, and victories feel "
        "earned and momentous.",
        "image_url": "/assets/catalog/tones/heroic-epic_9206142b.jpg",
    },
    {
        "id": "melancholic-somber",
        "name": "Melancholic & Somber",
        "description": "Reflective and quiet, focused on loss and faded glory.",
        "instruction": "Use quiet, reflective language and a slow pace. Dwell on loss, memory and "
        "the beauty in what is fading; hope is small, fragile and precious.",
        "image_url": "/assets/catalog/tones/melancholic-somber_e5a53a82.jpg",
    },
    {
        "id": "post-apocalyptic",
        "name": "Post-Apocalyptic Despair",
        "description": "Bleak survival among the ruins of a lost world.",
        "instruction": "Show a world after the fall: scarce resources, ruins that remember better "
        "times, and survivors shaped by hard choices. Trust is rare and every gain "
        "has a price.",
        "image_url": "/assets/catalog/tones/post-apocalyptic-despair_cef1270d.jpg",
    },
    {
        "id": "cozy-whimsy",
        "name": "Cozy & Whimsical",
        "description": "Lighthearted magic and the warmth of companionship.",
        "instruction": "Keep the stakes low and the heart warm: gentle humor, small magical "
        "wonders, kind strangers and problems solved with cleverness and friendship "
        "rather than force.",
        "image_url": "/assets/catalog/tones/cozy-whimsical_5c43d53c.jpg",
    },
    {
        "id": "political-intrigue",
        "name": "Political Intrigue",
        "description": "Hidden agendas, power plays and dangerous diplomacy.",
        "instruction": "Every character wants something and hides something. Drive the story "
        "through negotiations, leverage, shifting alliances and secrets whose "
        "reveal changes the balance of power.",
        "image_url": "/assets/catalog/tones/political-intrigue_2396d222.jpg",
    },
    {
        "id": "cosmic-horror",
        "name": "Cosmic Horror",
        "description": "Existential dread and incomprehensible ancient forces.",
        "instruction": "Hint at forces too vast to understand, never show them fully. Knowledge "
        "comes at a cost to the mind, and the deeper the protagonist looks, the "
        "smaller humanity seems.",
        "image_url": "/assets/catalog/tones/cosmic-horror_8e1a9584.jpg",
    },
    {
        "id": "noir-detective",
        "name": "Noir Detective",
        "description": "Clue hunting and gritty moral ambiguity.",
        "instruction": "Narrate with a weary, observant voice. Reward careful attention to clues "
        "and lies, and let the truth be uncomfortable: justice and crime are rarely "
        "clean.",
        "image_url": "/assets/catalog/tones/noir-detective-crime_16d8363f.jpg",
    },
    {
        "id": "absurd-slapstick",
        "name": "Absurd Slapstick",
        "description": "Ridiculous physical comedy and deadpan reactions.",
        "instruction": "Undermine every serious moment with absurd coincidences, over-the-top "
        "physical comedy and characters who react with complete deadpan calm.",
        "image_url": "/assets/catalog/tones/absurd-slapstick_42e21daa.jpg",
    },
    {
        "id": "survival-grit",
        "name": "Survival Grit",
        "description": "Hunger, cold and exhaustion: every resource counts.",
        "instruction": "Make survival the core tension: food, water, warmth, light and health run "
        "low, injuries linger and nature is indifferent. Small wins like a fire or "
        "a dry shelter feel huge; choices are practical and often painful.",
        "image_url": None,
    },
    {
        "id": "stranded-sci-fi",
        "name": "Stranded in the Stars",
        "description": "Cut off on a hostile world with failing technology.",
        "instruction": "The protagonist is stranded far from help: air, power and spare parts are "
        "limited, systems fail at the worst moment and the environment is alien and "
        "lethal. Ingenuity, improvised repairs and grim calculation drive the "
        "story.",
        "image_url": None,
    },
    {
        "id": "survival-horror",
        "name": "Survival Horror",
        "description": "Scarce means against a threat that keeps hunting.",
        "instruction": "Combine dread with scarcity: few weapons, little ammunition, unreliable "
        "light and a threat that is stronger than the protagonist. Running and "
        "hiding are often wiser than fighting, and safe places never stay safe for "
        "long.",
        "image_url": None,
    },
    {
        "id": "heist-caper",
        "name": "Heist & Caper",
        "description": "Clever plans, sudden twists and cool banter.",
        "instruction": "Build the story around a plan: casing the target, assembling the crew, and "
        "the moment everything goes wrong. Reward cleverness, keep the banter sharp "
        "and save one twist for the end.",
        "image_url": None,
    },
    {
        "id": "fairy-tale-folklore",
        "name": "Fairy-Tale Folklore",
        "description": "Old rules, curses and bargains with spirits.",
        "instruction": "Tell it like an old tale: the world follows strange but strict rules, "
        "promises bind, names have power and spirits bargain. Kindness and wit "
        "matter more than strength, and every gift has a hidden price.",
        "image_url": None,
    },
    {
        "id": "gothic-romance",
        "name": "Gothic Romance",
        "description": "Forbidden love, old houses and buried secrets.",
        "instruction": "Mix longing and dread: a decaying house or bloodline, a dangerous "
        "attraction and secrets the past refuses to bury. Let emotions run high and "
        "atmosphere carry the story.",
        "image_url": None,
    },
    {
        "id": "cozy-mystery",
        "name": "Cozy Mystery",
        "description": "A whodunit without brutality in a close-knit place.",
        "instruction": "Keep it a puzzle among neighbors: a crime in a small community, quirky "
        "suspects with secrets, fair clues and red herrings. Violence stays "
        "offstage, and the solution feels earned.",
        "image_url": None,
    },
    {
        "id": "pulp-adventure",
        "name": "Pulp Adventure",
        "description": "Cliffhangers, deadly traps and exotic places.",
        "instruction": "Move fast from peril to peril: lost ruins, ticking traps, daring escapes "
        "and villains with grand schemes. End scenes on cliffhangers and let "
        "bravado win the day.",
        "image_url": None,
    },
    {
        "id": "psychological-thriller",
        "name": "Psychological Thriller",
        "description": "Unreliable perception, paranoia and creeping doubt.",
        "instruction": "Make the protagonist doubt what is real: contradictory clues, people who "
        "might be lying and memories that do not fit. Tension comes from not "
        "knowing whom to trust, including oneself.",
        "image_url": None,
    },
    {
        "id": "war-drama",
        "name": "War Drama",
        "description": "Comradeship, hard orders and the cost of violence.",
        "instruction": "Show war from the ground: bonds between comrades, orders that demand "
        "terrible choices and losses that are not forgotten. Never glorify "
        "violence; every victory has a cost.",
        "image_url": None,
    },
    {
        "id": "coming-of-age",
        "name": "Coming of Age",
        "description": "Growing up, friendship and first real choices.",
        "instruction": "Focus on change: first responsibilities, friendships tested, mistakes that "
        "teach and the moment of stepping out of someone's shadow. Warmth and "
        "awkwardness sit side by side.",
        "image_url": None,
    },
    {
        "id": "weird-west",
        "name": "Weird West",
        "description": "Frontier grit meets the supernatural.",
        "instruction": "Tell a Western where the frontier hides more than outlaws: dusty towns, "
        "hard justice, long rides and something uncanny under the sand. Keep the "
        "dialogue laconic and the supernatural unsettling.",
        "image_url": None,
    },
    {
        "id": "solarpunk-hope",
        "name": "Solarpunk Hope",
        "description": "Rebuilding a better world through community and ingenuity.",
        "instruction": "Show a future worth building: communities that cooperate, technology in "
        "harmony with nature and problems solved through ingenuity and solidarity. "
        "Conflicts are real but hope is stronger.",
        "image_url": None,
    },
]
