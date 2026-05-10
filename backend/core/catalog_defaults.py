from typing import Any

DEFAULT_IMAGE_STYLES: list[dict[str, Any]] = [   {   'description': 'Moody brushwork with dramatic contrast and medieval '
                       'grit.',
        'id': 'dark-fantasy-painting',
        'image_url': '/assets/catalog/styles/dark-fantasy-painting_35657e9e.jpg',
        'instruction': 'dark fantasy painting, dramatic chiaroscuro, textured '
                       'brush strokes, rich atmosphere',
        'name': 'Dark Fantasy Painting'},
    {   'description': 'Film-like composition with realistic lighting and '
                       'depth.',
        'id': 'cinematic-realism',
        'image_url': '/assets/catalog/styles/cinematic-realism_bd485f41.jpg',
        'instruction': 'cinematic realism, volumetric lighting, detailed '
                       'environment, film still composition',
        'name': 'Cinematic Realism'},
    {   'description': 'Bold outlines, vivid palettes, and heroic fantasy '
                       'readability.',
        'id': 'stylized-rpg-art',
        'image_url': '/assets/catalog/styles/stylized-rpg-art_db5e95d6.jpg',
        'instruction': 'stylized RPG concept art, clean silhouettes, vibrant '
                       'but grounded colors',
        'name': 'Stylized RPG Art'},
    {   'description': 'Raw, hand-drawn aesthetic with heavy ink washes and '
                       'scratched textures.',
        'id': 'grimdark-ink-sketch',
        'image_url': '/assets/catalog/styles/grimdark-ink-sketch_023b9ad4.jpg',
        'instruction': 'grimdark ink sketch, cross-hatching, distressed paper '
                       'texture, high contrast black and white',
        'name': 'Grimdark Ink Sketch'},
    {   'description': 'Vibrant neon lights, rainy cityscapes, and high-tech '
                       'grit.',
        'id': 'cyberpunk-neon',
        'image_url': '/assets/catalog/styles/cyberpunk-neon_e4b9fd38.jpg',
        'instruction': 'cyberpunk aesthetic, synthwave colors, neon glow, wet '
                       'asphalt reflections, futuristic noir',
        'name': 'Cyberpunk Neon'},
    {   'description': 'Soft, bleeding colors with a dreamlike, mystical '
                       'atmosphere.',
        'id': 'ethereal-watercolor',
        'image_url': '/assets/catalog/styles/ethereal-watercolor_963ce2cd.jpg',
        'instruction': 'ethereal watercolor painting, soft edges, bleeding '
                       'pigments, mystical light, dreamy pastel tones',
        'name': 'Ethereal Watercolor'},
    {   'description': 'Futuristic tech, vast space, and advanced starships.',
        'id': 'science-fiction',
        'image_url': '/assets/catalog/styles/science-fiction_93659096.jpg',
        'instruction': 'futuristic science fiction world, starships in the '
                       'sky, sleek high tech architecture, glowing neon '
                       'lights, cinematic composition',
        'name': 'Science-Fiction'},
    {   'description': 'Classic 90s adventure style with vibrant colors and '
                       'charming pixels.',
        'id': 'pixelart',
        'image_url': '/assets/catalog/styles/pixelart_5fb230a4.jpg',
        'instruction': '90s point and click adventure game pixel art, '
                       'LucasArts style, vibrant limited color palette, '
                       'pixelated aesthetic',
        'name': 'Pixelart'},
    {   'description': 'High-contrast black and white with dramatic shadows, '
                       'rainy streets, and a 1940s mystery atmosphere.',
        'id': 'classic-film-noir',
        'image_url': '/assets/catalog/styles/classic-film-noir_73cadd52.jpg',
        'instruction': 'Classic film noir, high contrast black and white, hard '
                       'shadows, chiaroscuro lighting, rainy urban streets, '
                       'Venetian blind shadows, 1940s cinematic aesthetic, '
                       'grainy film texture.',
        'name': 'Classic Film Noir'},
    {   'description': 'Hand-painted lush landscapes and soft, nostalgic '
                       'lighting inspired by classic Japanese animation.',
        'id': 'ghibli-esque-whimsy',
        'image_url': '/assets/catalog/styles/ghibli-esque-whimsy_37636857.jpg',
        'instruction': 'Studio Ghibli style, hand-painted aesthetic, lush '
                       'green nature, soft morning light, vibrant but gentle '
                       'colors, whimsical atmosphere, highly detailed '
                       'background art.',
        'name': 'Ghibli-esque Whimsy'},
    {   'description': '80s retro-futurism with neon purple gradients, '
                       'wireframe grids, and glowing digital horizons.',
        'id': 'retro-synthwave',
        'image_url': '/assets/catalog/styles/retro-synthwave_47522b15.jpg',
        'instruction': 'Synthwave aesthetic, 1980s retro-futurism, neon pink '
                       'and electric blue palette, glowing grid floor, retro '
                       'sun, digital glitch effects, vibrant cyber-dream.',
        'name': 'Retro Synthwave'},
    {   'description': 'An eerie fusion of biology and machinery with dark '
                       'metallic textures and skeletal structures.',
        'id': 'bio-organic-gothic',
        'image_url': '/assets/catalog/styles/bio-organic-gothic_23707b39.jpg',
        'instruction': 'Bio-organic gothic, xenomorphic architecture, fused '
                       'bone and cold metal, dark monochrome with slime '
                       'highlights, eerie atmosphere, intricate mechanical '
                       'biological details.',
        'name': 'Bio-Organic Gothic'},
    {   'description': 'Expressive oil painting with thick palette knife '
                       'strokes, visible textures, and a focus on the play of '
                       'light.',
        'id': 'impressionist-oil',
        'image_url': '/assets/catalog/styles/impressionist-oil_801143d7.jpg',
        'instruction': 'Impressionist oil painting, thick impasto texture, '
                       'visible palette knife strokes, vibrant color dabs, '
                       'expressive light and shadow, romanticized atmosphere, '
                       'canvas texture.',
        'name': 'Impressionist Oil'},
    {   'description': 'Sharp line art, dynamic action poses, and vibrant '
                       'digital effects common in modern high-budget '
                       'animation.',
        'id': 'modern-shonen-anime',
        'image_url': '/assets/catalog/styles/modern-shonen-anime_7417820f.jpg',
        'instruction': 'Modern shonen anime style, crisp line art, dynamic '
                       'cinematic lighting, vibrant cel-shading, high-octane '
                       'energy, digital animation aesthetic, sharp focus, '
                       'vivid special effects.',
        'name': 'Modern Shonen Anime'},
    {   'description': 'Bold outlines, dynamic Ben-Day dots, and vibrant '
                       'primary colors typical of classic Silver Age comics.',
        'id': 'classical-heroic-comic',
        'image_url': '/assets/catalog/styles/classical-heroic-comic_8970c6ab.jpg',
        'instruction': 'Classical comic book style, bold black ink outlines, '
                       'Ben-Day dot shading, vibrant primary color palette, '
                       'dynamic action composition, Silver Age comic '
                       'aesthetic, dramatic shadows.',
        'name': 'Classical Comic'},
    {   'description': 'Bold outlines, dynamic Ben-Day dots, and vibrant '
                       'primary colors typical of classic Silver Age superhero '
                       'comics.',
        'id': 'heroic-comic',
        'image_url': '/assets/catalog/styles/heroic-comic.jpg',
        'instruction': 'Classical heroic comic book style, bold black ink '
                       'outlines, Ben-Day dot shading, vibrant primary color '
                       'palette, dynamic action composition, Silver Age comic '
                       'aesthetic, dramatic shadows.',
        'name': 'Classical Heroic Comic'}]

DEFAULT_TONES: list[dict[str, Any]] = [   {   'description': 'Dread, uncertainty, and escalating psychological '
                       'pressure.',
        'id': 'horror',
        'image_url': '/assets/catalog/tones/horror_7e4a6db5.jpg',
        'instruction': 'Maintain unsettling tension, sparse comfort, and '
                       'consequences that feel dangerous.',
        'name': 'Horror'},
    {   'description': 'Futuristic systems, unknown tech, and speculative '
                       'mystery.',
        'id': 'sci-fi',
        'image_url': '/assets/catalog/tones/sci-fi_0b2e548f.jpg',
        'instruction': 'Use futuristic world logic, technical flavor, and '
                       'discovery-driven narrative beats.',
        'name': 'Sci-Fi'},
    {   'description': 'Comedic misunderstandings, playful pacing, and '
                       'memorable banter.',
        'id': 'sitcom',
        'image_url': '/assets/catalog/tones/sitcom_3b747e63.jpg',
        'instruction': 'Favor witty dialogue, comic timing, and low-stakes '
                       'chaos with charming setbacks.',
        'name': 'Sitcom'},
    {   'description': 'Heroic quest tone with balanced drama and wonder.',
        'id': 'classic-rpg',
        'image_url': '/assets/catalog/tones/classic-rpg_551efe58.jpg',
        'instruction': 'Keep a classic heroic arc, meaningful choices, and '
                       'clear quest momentum.',
        'name': 'Classic RPG'},
    {   'description': 'Grand scale, legendary deeds, and inspiring bravery.',
        'id': 'heroic-epic',
        'image_url': '/assets/catalog/tones/heroic-epic_9206142b.jpg',
        'instruction': 'The tone is heroic and epic. Focus on grand scale, '
                       'legendary atmosphere, and inspiring narratives.',
        'name': 'Heroic & Epic'},
    {   'description': 'Reflective, sad, and focused on loss or faded glory.',
        'id': 'melancholic-somber',
        'image_url': '/assets/catalog/tones/melancholic-somber_e5a53a82.jpg',
        'instruction': 'The tone is melancholic and somber. Use reflective '
                       'language, focus on themes of loss and beauty in '
                       'sadness.',
        'name': 'Melancholic & Somber'},
    {   'description': 'Bleak and resource-focused, with themes of survival '
                       'and the haunting memories of a lost world.',
        'id': 'post-apocalyptic-despair',
        'image_url': '/assets/catalog/tones/post-apocalyptic-despair_cef1270d.jpg',
        'instruction': 'The tone is post-apocalyptic and bleak. Focus on the '
                       'struggle for survival, scarcity of resources, faded '
                       'glory of the old world, and the harsh, unforgiving '
                       'reality of the present.',
        'name': 'Post-Apocalyptic Despair'},
    {   'description': 'Lighthearted and magical, emphasizing small joys, '
                       'wonder, and the warmth of friendship.',
        'id': 'cozy-whimsical',
        'image_url': '/assets/catalog/tones/cozy-whimsical_5c43d53c.jpg',
        'instruction': 'Maintain a cozy and whimsical tone. Focus on magical '
                       'wonder, gentle humor, low-stakes conflict, and the '
                       'heartwarming aspects of exploration and companionship.',
        'name': 'Cozy & Whimsical'},
    {   'description': 'A web of lies, hidden motives, and social maneuvering '
                       'where words are as dangerous as swords.',
        'id': 'political-intrigue',
        'image_url': '/assets/catalog/tones/political-intrigue_2396d222.jpg',
        'instruction': 'The tone is one of political intrigue and social '
                       'complexity. Focus on hidden agendas, subtle power '
                       'plays, high-stakes diplomacy, and the tension of '
                       'keeping secrets in a world of lies.',
        'name': 'Political Intrigue'},
    {   'description': 'Existential dread and mind-bending mysteries that '
                       'emphasize the insignificance of humanity.',
        'id': 'cosmic-horror',
        'image_url': '/assets/catalog/tones/cosmic-horror_8e1a9584.jpg',
        'instruction': 'Invoke a sense of cosmic horror. Focus on existential '
                       'dread, incomprehensible ancient forces, the fragility '
                       'of the human mind, and mysteries that are better left '
                       'unsolved.',
        'name': 'Cosmic Horror'},
    {   'description': 'Gritty and analytical, focusing on clues, suspects, '
                       'and the moral gray areas of the law.',
        'id': 'noir-detective-crime',
        'image_url': '/assets/catalog/tones/noir-detective-crime_16d8363f.jpg',
        'instruction': 'Adopt a noir detective tone. Focus on analytical '
                       'observation, the search for clues, gritty underworld '
                       'atmosphere, and the moral ambiguity of justice and '
                       'crime.',
        'name': 'Noir Detective (Crime)'},
    {   'description': 'Deadpan humor, ridiculous coincidences, and '
                       'nonsensical reactions to serious situations.',
        'id': 'absurd-slapstick',
        'image_url': '/assets/catalog/tones/absurd-slapstick_42e21daa.jpg',
        'instruction': 'The tone is absurd slapstick. Use deadpan humor, '
                       'emphasize ridiculous physical comedy, nonsensical '
                       'dialogue, and over-the-top reactions. Serious '
                       'situations should be undermined by absurdity and '
                       'bizarre coincidences.',
        'name': 'Absurd Slapstick'}]
