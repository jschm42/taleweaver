from typing import Any

DEFAULT_IMAGE_STYLES: list[dict[str, Any]] = [
    {
        "id": "dark-fantasy-painting",
        "name": "Dark Fantasy Painting",
        "description": "Moody oil painting with dramatic contrast and medieval grit.",
        "instruction": "dark fantasy oil painting, dramatic chiaroscuro, visible textured "
        "brushwork, deep shadows with warm firelight highlights, muted earthy "
        "palette with ember accents, weathered medieval materials, atmospheric haze",
        "image_url": "/assets/catalog/styles/21a67697_dark-fantasy-painting.webp",
    },
    {
        "id": "cinematic-realism",
        "name": "Cinematic Realism",
        "description": "Photorealistic film stills with motivated lighting and depth.",
        "instruction": "cinematic photorealism, film still look, widescreen framing, motivated "
        "natural and practical lighting, volumetric light, rich but natural color "
        "grade, shallow depth of field, realistic materials and skin texture, fine "
        "film grain",
        "image_url": "/assets/catalog/styles/2cb03a4a_cinematic-realism.webp",
    },
    {
        "id": "stylized-rpg-art",
        "name": "Stylized RPG Art",
        "description": "Hand-painted game art with clean silhouettes and vivid, grounded colors.",
        "instruction": "stylized RPG concept art, hand-painted digital illustration, clean "
        "readable silhouettes, slightly exaggerated proportions, soft cel-like "
        "shading with painted textures, vibrant but grounded palette, clear focal "
        "point",
        "image_url": "/assets/catalog/styles/9f1895ef_stylized-rpg-art.webp",
    },
    {
        "id": "grimdark-ink-sketch",
        "name": "Grimdark Ink Sketch",
        "description": "Raw pen-and-ink drawing with heavy washes and scratched textures.",
        "instruction": "grimdark pen and ink illustration, dense cross-hatching, scratchy "
        "expressive linework, heavy black ink washes, dry-brush and splatter "
        "texture, aged distressed paper, stark black and white, no color",
        "image_url": "/assets/catalog/styles/4b761143_grimdark-ink-sketch.webp",
    },
    {
        "id": "cyberpunk-neon",
        "name": "Cyberpunk Neon",
        "description": "Neon-lit high tech with grime, haze and reflective surfaces.",
        "instruction": "cyberpunk aesthetic, high-tech low-life detail, saturated magenta and cyan "
        "neon light against deep shadow, reflective wet surfaces, holographic glow, "
        "haze, grime on chrome and plastic, futuristic noir mood",
        "image_url": "/assets/catalog/styles/3823ee64_cyberpunk-neon.webp",
    },
    {
        "id": "ethereal-watercolor",
        "name": "Ethereal Watercolor",
        "description": "Soft, bleeding watercolor with a dreamlike, mystical light.",
        "instruction": "ethereal watercolor painting, wet-on-wet washes, soft bleeding edges, "
        "granulating pigment, white paper glowing through, gentle luminous light, "
        "dreamy pastel palette, delicate loose linework",
        "image_url": "/assets/catalog/styles/e83fcf1c_ethereal-watercolor.webp",
    },
    {
        "id": "science-fiction",
        "name": "Science-Fiction",
        "description": "Sleek, advanced technology rendered as clean concept art.",
        "instruction": "clean science fiction concept art, sleek hard-surface design, precise "
        "industrial detail, cool blue-white lighting with glowing interface "
        "accents, polished metal, glass and composite materials, cinematic wide "
        "composition",
        "image_url": "/assets/catalog/styles/4efc432a_science-fiction.webp",
    },
    {
        "id": "pixelart",
        "name": "Pixelart",
        "description": "Classic 90s adventure game look with crisp pixels and a limited palette.",
        "instruction": "16-bit pixel art in the look of 1990s point-and-click adventure games, "
        "crisp visible pixels, limited color palette with dithering, hand-placed "
        "detail, no anti-aliasing, no blur, no text, no user interface",
        "image_url": "/assets/catalog/styles/013c3c73_pixelart.webp",
    },
    {
        "id": "film-noir",
        "name": "Film Noir",
        "description": "High-contrast black and white with hard shadows and smoky haze.",
        "instruction": "classic film noir, black and white 1940s cinematography, hard low-key "
        "lighting, deep shadows with bright edge highlights, strong chiaroscuro, "
        "slanted light patterns, smoky haze, grainy film texture, no color",
        "image_url": "/assets/catalog/styles/2db52151_film-noir.webp",
    },
    {
        "id": "ghibli-whimsy",
        "name": "Ghibli-esque Whimsy",
        "description": "Hand-painted animation backgrounds with lush nature and nostalgic light.",
        "instruction": "hand-painted 2D animation background art, soft gouache and watercolor "
        "textures, gentle clean line art, lush detailed nature, warm nostalgic "
        "sunlight, soft rich palette, whimsical cozy atmosphere",
        "image_url": "/assets/catalog/styles/129ca73e_ghibli-whimsy.webp",
    },
    {
        "id": "retro-synthwave",
        "name": "Retro Synthwave",
        "description": "80s retro-futurism in glowing neon pink, violet and electric blue.",
        "instruction": "1980s synthwave retro-futurism, glowing neon pink, violet and electric "
        "blue palette, chrome highlights, sunset gradients, glowing wireframe "
        "accents, soft bloom, VHS scanline texture, airbrushed album-cover finish",
        "image_url": "/assets/catalog/styles/cdbebc19_retro-synthwave.webp",
    },
    {
        "id": "bio-organic-gothic",
        "name": "Bio-Organic Gothic",
        "description": "Eerie fusion of biology and machinery in dark, skeletal detail.",
        "instruction": "bio-mechanical gothic art, organic and mechanical forms fused together, "
        "ribbed bone-like structures, cables like sinews, glossy wet surfaces and "
        "cold metal, near-monochrome black, bone and grey-green palette, low eerie "
        "light, intricate unsettling detail",
        "image_url": "/assets/catalog/styles/3172f6f1_bio-organic-gothic.webp",
    },
    {
        "id": "impressionist-oil",
        "name": "Impressionist Oil",
        "description": "Expressive oil painting with thick impasto and shimmering light.",
        "instruction": "impressionist oil painting, thick impasto, visible broken brush and "
        "palette-knife strokes, dabs of pure color, shimmering natural light, soft "
        "edges, romantic atmosphere, visible canvas texture",
        "image_url": "/assets/catalog/styles/fa1c3e22_impressionist-oil.webp",
    },
    {
        "id": "shonen-anime",
        "name": "Modern Shonen Anime",
        "description": "Crisp line art, bold cel shading and high-energy lighting.",
        "instruction": "modern action anime key visual, crisp clean line art, bold cel shading "
        "with sharp shadow shapes, dynamic camera angle, dramatic rim light, "
        "saturated colors, energetic glowing effects, sharp focus",
        "image_url": "/assets/catalog/styles/47e0a625_shonen-anime.webp",
    },
    {
        "id": "classical-comic",
        "name": "Classical Comic",
        "description": "Bold outlines, Ben-Day dots and vibrant primary colors of Silver Age "
        "comics.",
        "instruction": "Silver Age comic book art, bold black ink outlines, flat primary colors "
        "with Ben-Day halftone dots, dramatic spot blacks, dynamic composition, "
        "printed paper texture, no text, no speech bubbles, no captions",
        "image_url": "/assets/catalog/styles/62cd1c91_classical-comic.webp",
    },
    {
        "id": "survival-science-fiction",
        "name": "Survival Science Fiction",
        "description": "Stranded on hostile worlds: worn, patched and improvised technology.",
        "instruction": "survival science fiction concept art, worn and improvised technology, "
        "scratched and patched hard-surface materials, dust, frost and grime, harsh "
        "alien light, desaturated palette with cold teal and warning-orange "
        "accents, haze, grounded realism, isolation and scarcity",
        "image_url": "/assets/catalog/styles/727022ea_survival-science-fiction.webp",
    },
    {
        "id": "survival-rpg",
        "name": "Survival RPG",
        "description": "Gritty, readable game art of handmade gear and harsh wilderness.",
        "instruction": "survival RPG concept art, painterly game illustration, clear readable "
        "silhouettes, handcrafted and weathered materials like rope, hide, rough "
        "wood and rusted metal, earthy muted palette with warm firelight accents, "
        "natural overcast light, gritty but legible detail",
        "image_url": "/assets/catalog/styles/46a800ac_survival-rpg.webp",
    },
    {
        "id": "survival-realism",
        "name": "Survival Realism",
        "description": "Documentary photo look: real materials, natural light, no glamour.",
        "instruction": "photorealistic survival realism, documentary photography look, natural "
        "available light, overcast sky or low sun, 35mm lens, real materials with "
        "mud, wear and moisture, desaturated earthy color grade, fine film grain, "
        "no stylization, no magical glow",
        "image_url": "/assets/catalog/styles/32a42339_survival-realism.webp",
    },
    {
        "id": "storybook-gouache",
        "name": "Storybook Gouache",
        "description": "Warm, matte picture-book painting with gentle charm.",
        "instruction": "children's picture book illustration, opaque gouache painting, matte "
        "chalky texture, soft rounded shapes, warm limited palette, gentle diffused "
        "light, visible paper grain, charming and inviting",
        "image_url": "/assets/catalog/styles/da1c88b2_storybook-gouache.webp",
    },
    {
        "id": "ukiyo-e-woodblock",
        "name": "Ukiyo-e Woodblock",
        "description": "Flat colors and bold lines of Japanese woodblock prints.",
        "instruction": "ukiyo-e woodblock print, bold flowing outlines, flat areas of color, "
        "subtle bokashi gradients, stylized waves, clouds and wind lines, muted "
        "indigo, vermilion and ochre palette, washi paper texture, no text",
        "image_url": "/assets/catalog/styles/23e79c6c_ukiyo-e-woodblock.webp",
    },
    {
        "id": "victorian-engraving",
        "name": "Victorian Engraving",
        "description": "Fine steel-engraving hatching of 19th-century books.",
        "instruction": "19th-century steel engraving illustration, fine parallel line hatching and "
        "cross-hatching, stippled shading, meticulous detail, monochrome ink on "
        "aged cream paper, encyclopedia plate look, no color",
        "image_url": "/assets/catalog/styles/74d15583_victorian-engraving.webp",
    },
    {
        "id": "art-nouveau",
        "name": "Art Nouveau",
        "description": "Ornamental frames, flowing lines and elegant natural forms.",
        "instruction": "Art Nouveau illustration, sinuous whiplash lines, ornamental floral "
        "borders, elegant stylized figures, flat decorative color areas with gold "
        "accents, muted sage, ochre and rose palette, poster lithograph texture, no "
        "text",
        "image_url": "/assets/catalog/styles/6ecb8f54_art-nouveau.webp",
    },
    {
        "id": "isometric-diorama",
        "name": "Isometric Diorama",
        "description": "A detailed miniature world seen from above at an angle.",
        "instruction": "isometric miniature diorama, three-quarter top-down view, tilt-shift depth "
        "of field, tiny highly detailed props, soft global illumination, clean "
        "readable layout, toy-like scale, cohesive palette",
        "image_url": "/assets/catalog/styles/f893489c_isometric-diorama.webp",
    },
    {
        "id": "low-poly-3d",
        "name": "Low-Poly 3D",
        "description": "Stylized game look with faceted shapes and clean light.",
        "instruction": "low-poly 3D render, flat-shaded faceted geometry, simple clean shapes, "
        "soft ambient occlusion, gentle directional light, harmonious pastel and "
        "earthy palette, stylized indie game look",
        "image_url": "/assets/catalog/styles/47d8e1b7_low-poly-3d.webp",
    },
    {
        "id": "claymation",
        "name": "Claymation",
        "description": "Handmade stop-motion look with clay and fingerprints.",
        "instruction": "stop-motion claymation, handmade plasticine characters and sets, visible "
        "fingerprints and tool marks, slightly lumpy shapes, miniature practical "
        "lighting, shallow depth of field, playful saturated colors",
        "image_url": "/assets/catalog/styles/5270631c_claymation.webp",
    },
    {
        "id": "stained-glass",
        "name": "Stained Glass",
        "description": "Luminous colored glass framed by dark lead lines.",
        "instruction": "stained glass window art, jewel-toned translucent glass panels, bold dark "
        "lead lines, light glowing through the glass, simplified symbolic figures, "
        "Gothic window composition, rich ruby, sapphire and gold palette",
        "image_url": "/assets/catalog/styles/d862bb50_stained-glass.webp",
    },
    {
        "id": "weird-west",
        "name": "Weird West",
        "description": "Dusty Frontier art with a supernatural edge.",
        "instruction": "weird west illustration, sun-bleached frontier landscapes, dust and heat "
        "haze, worn leather, wood and iron, low golden sun with long shadows, ochre "
        "and rust palette with eerie green accents, gritty painterly texture, "
        "uncanny undertone",
        "image_url": "/assets/catalog/styles/49a78586_weird-west.webp",
    },
    {
        "id": "solarpunk",
        "name": "Solarpunk",
        "description": "Bright, green and hopeful future of nature and technology.",
        "instruction": "solarpunk concept art, lush greenery woven into elegant sustainable "
        "architecture, solar sails and glass, warm bright daylight, clean saturated "
        "greens, whites and gold, optimistic and airy atmosphere, art nouveau "
        "inspired curves",
        "image_url": "/assets/catalog/styles/3c490a83_solarpunk.webp",
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
        "image_url": "/assets/catalog/tones/ed6cf1ea_horror.webp",
    },
    {
        "id": "sci-fi",
        "name": "Sci-Fi",
        "description": "Futuristic systems, unknown technology and speculative mystery.",
        "instruction": "Ground the future in believable technology and its social consequences. "
        "Drive the story through discovery, technical puzzles and the question of "
        "what the new means for people.",
        "image_url": "/assets/catalog/tones/e56b4e32_sci-fi.webp",
    },
    {
        "id": "sitcom",
        "name": "Sitcom",
        "description": "Comedic misunderstandings, playful pacing and memorable banter.",
        "instruction": "Favor witty dialogue, running gags, comic timing and low-stakes chaos. "
        "Setbacks are charming rather than cruel, and every scene ends on a beat "
        "that lands.",
        "image_url": "/assets/catalog/tones/8e8440c6_sitcom.webp",
    },
    {
        "id": "classic-rpg",
        "name": "Classic RPG",
        "description": "Heroic quests with balanced drama and wonder.",
        "instruction": "Keep a clear quest structure with meaningful choices, memorable allies and "
        "rivals, and a steady balance of danger, discovery and reward.",
        "image_url": "/assets/catalog/tones/5fe78e50_classic-rpg.webp",
    },
    {
        "id": "heroic-epic",
        "name": "Heroic & Epic",
        "description": "Grand scale, legendary deeds and inspiring bravery.",
        "instruction": "Tell the story on a grand scale: ancient stakes, legendary places and "
        "deeds that will be sung about. Courage is costly, and victories feel "
        "earned and momentous.",
        "image_url": "/assets/catalog/tones/2a878790_heroic-epic.webp",
    },
    {
        "id": "melancholic-somber",
        "name": "Melancholic & Somber",
        "description": "Reflective and quiet, focused on loss and faded glory.",
        "instruction": "Use quiet, reflective language and a slow pace. Dwell on loss, memory and "
        "the beauty in what is fading; hope is small, fragile and precious.",
        "image_url": "/assets/catalog/tones/198e5ac7_melancholic-somber.webp",
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
        "image_url": "/assets/catalog/tones/d176947d_political-intrigue.webp",
    },
    {
        "id": "cosmic-horror",
        "name": "Cosmic Horror",
        "description": "Existential dread and incomprehensible ancient forces.",
        "instruction": "Hint at forces too vast to understand, never show them fully. Knowledge "
        "comes at a cost to the mind, and the deeper the protagonist looks, the "
        "smaller humanity seems.",
        "image_url": "/assets/catalog/tones/a1dbace1_cosmic-horror.webp",
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
        "image_url": "/assets/catalog/tones/3c2ea8cf_absurd-slapstick.webp",
    },
    {
        "id": "survival-grit",
        "name": "Survival Grit",
        "description": "Hunger, cold and exhaustion: every resource counts.",
        "instruction": "Make survival the core tension: food, water, warmth, light and health run "
        "low, injuries linger and nature is indifferent. Small wins like a fire or "
        "a dry shelter feel huge; choices are practical and often painful.",
        "image_url": "/assets/catalog/tones/931d49ce_survival-grit.webp",
    },
    {
        "id": "stranded-sci-fi",
        "name": "Stranded in the Stars",
        "description": "Cut off on a hostile world with failing technology.",
        "instruction": "The protagonist is stranded far from help: air, power and spare parts are "
        "limited, systems fail at the worst moment and the environment is alien and "
        "lethal. Ingenuity, improvised repairs and grim calculation drive the "
        "story.",
        "image_url": "/assets/catalog/tones/fbe4d054_stranded-sci-fi.webp",
    },
    {
        "id": "survival-horror",
        "name": "Survival Horror",
        "description": "Scarce means against a threat that keeps hunting.",
        "instruction": "Combine dread with scarcity: few weapons, little ammunition, unreliable "
        "light and a threat that is stronger than the protagonist. Running and "
        "hiding are often wiser than fighting, and safe places never stay safe for "
        "long.",
        "image_url": "/assets/catalog/tones/56c26707_survival-horror.webp",
    },
    {
        "id": "heist-caper",
        "name": "Heist & Caper",
        "description": "Clever plans, sudden twists and cool banter.",
        "instruction": "Build the story around a plan: casing the target, assembling the crew, and "
        "the moment everything goes wrong. Reward cleverness, keep the banter sharp "
        "and save one twist for the end.",
        "image_url": "/assets/catalog/tones/c46fbc7a_heist-caper.webp",
    },
    {
        "id": "fairy-tale-folklore",
        "name": "Fairy-Tale Folklore",
        "description": "Old rules, curses and bargains with spirits.",
        "instruction": "Tell it like an old tale: the world follows strange but strict rules, "
        "promises bind, names have power and spirits bargain. Kindness and wit "
        "matter more than strength, and every gift has a hidden price.",
        "image_url": "/assets/catalog/tones/32f470c4_fairy-tale-folklore.webp",
    },
    {
        "id": "gothic-romance",
        "name": "Gothic Romance",
        "description": "Forbidden love, old houses and buried secrets.",
        "instruction": "Mix longing and dread: a decaying house or bloodline, a dangerous "
        "attraction and secrets the past refuses to bury. Let emotions run high and "
        "atmosphere carry the story.",
        "image_url": "/assets/catalog/tones/cf1cf0ba_gothic-romance.webp",
    },
    {
        "id": "cozy-mystery",
        "name": "Cozy Mystery",
        "description": "A whodunit without brutality in a close-knit place.",
        "instruction": "Keep it a puzzle among neighbors: a crime in a small community, quirky "
        "suspects with secrets, fair clues and red herrings. Violence stays "
        "offstage, and the solution feels earned.",
        "image_url": "/assets/catalog/tones/0008e42e_cozy-mystery.webp",
    },
    {
        "id": "pulp-adventure",
        "name": "Pulp Adventure",
        "description": "Cliffhangers, deadly traps and exotic places.",
        "instruction": "Move fast from peril to peril: lost ruins, ticking traps, daring escapes "
        "and villains with grand schemes. End scenes on cliffhangers and let "
        "bravado win the day.",
        "image_url": "/assets/catalog/tones/16af6837_pulp-adventure.webp",
    },
    {
        "id": "psychological-thriller",
        "name": "Psychological Thriller",
        "description": "Unreliable perception, paranoia and creeping doubt.",
        "instruction": "Make the protagonist doubt what is real: contradictory clues, people who "
        "might be lying and memories that do not fit. Tension comes from not "
        "knowing whom to trust, including oneself.",
        "image_url": "/assets/catalog/tones/1f79ee95_psychological-thriller.webp",
    },
    {
        "id": "war-drama",
        "name": "War Drama",
        "description": "Comradeship, hard orders and the cost of violence.",
        "instruction": "Show war from the ground: bonds between comrades, orders that demand "
        "terrible choices and losses that are not forgotten. Never glorify "
        "violence; every victory has a cost.",
        "image_url": "/assets/catalog/tones/6f07ac92_war-drama.webp",
    },
    {
        "id": "coming-of-age",
        "name": "Coming of Age",
        "description": "Growing up, friendship and first real choices.",
        "instruction": "Focus on change: first responsibilities, friendships tested, mistakes that "
        "teach and the moment of stepping out of someone's shadow. Warmth and "
        "awkwardness sit side by side.",
        "image_url": "/assets/catalog/tones/fee71bd7_coming-of-age.webp",
    },
    {
        "id": "weird-west",
        "name": "Weird West",
        "description": "Frontier grit meets the supernatural.",
        "instruction": "Tell a Western where the frontier hides more than outlaws: dusty towns, "
        "hard justice, long rides and something uncanny under the sand. Keep the "
        "dialogue laconic and the supernatural unsettling.",
        "image_url": "/assets/catalog/tones/1f04a056_weird-west.webp",
    },
    {
        "id": "solarpunk-hope",
        "name": "Solarpunk Hope",
        "description": "Rebuilding a better world through community and ingenuity.",
        "instruction": "Show a future worth building: communities that cooperate, technology in "
        "harmony with nature and problems solved through ingenuity and solidarity. "
        "Conflicts are real but hope is stronger.",
        "image_url": "/assets/catalog/tones/4f14ea63_solarpunk-hope.webp",
    },
]
