# Adventure: Tante Emmas Naschkiste

## Story Idea
Es ist ein sonniger Samstagnachmittag. Der kleine Timi hat endlich seine Belohnung für das Rasenmähen erhalten: Eine glänzende 1-Euro-Münze. Sein Ziel: "Emmas Eckladen", der Ort, an dem Träume aus Zucker und Gelatine wahr werden. Doch der Weg zur perfekten bunten Tüte ist steinig. Ein griesgrämiger Nachbar bewacht den Eingang, eine verwirrte alte Dame blockiert die Lakritz-Abteilung, und der hinterhältige Kevin plant einen Süßigkeiten-Raubzug, der den ganzen Laden in Aufruhr versetzen könnte.

## Tone
**Nostalgisch & Humorvoll:** Warme Farben, der Duft von abgestandenem Kaffee und frischen Gummibärchen. Der Ton ist herzlich, aber leicht absurd. Snappy Dialoge, besonders von Angus, der einen dicken schottischen Akzent pflegt.

## Scenes (Locations)
1. **Vor dem Laden [ID: SHOP_FRONT]:** Ein Gehweg mit einem klapprigen Zeitungsständer. Hier residiert Herr Griesgram auf seiner Bank.
2. **Der Verkaufsraum [ID: MAIN_SHOP]:** Vollgestopft mit Regalen, Einmachgläsern und der heiligen Glasvitrine mit den losen Süßigkeiten. Hinter dem Tresen thront Angus.
3. **Die Schund-Ecke [ID: CRUSTY_CORNER]:** Ein dunklerer Bereich des Ladens mit alten Zeitschriften und reduzierten Konserven. Frau Schurbel scheint hier nach etwas Unsichtbarem zu suchen.
4. **Das Lager [ID: STORAGE_ROOM, is_hidden: true]:** Ein Ort voller Geheimnisse (und Vorräte), der nur mit Angus' Erlaubnis oder viel Geschick betreten werden kann.

## Characters (NPCs)
- **Angus McStorey [ID: NPC_ANGUS]:** Der LadenInhaber. Ein Schotte im Kilt (unter der Schürze), der jeden Satz mit "Aye" oder "Laddie" schmückt. Er nimmt sein Süßigkeiten-Handwerk sehr ernst.
- **Frau Schurbel [ID: NPC_SCHURBEL]:** Eine Stammkundin in einem Blumenkleid. Sie redet ununterbrochen über die "Zucker-Verschwörung der Marsmenschen" und sucht nach "intergalaktischem Senf".
- **Herr Griesgram [ID: NPC_GRIESGRAM]:** Der Nachbar von nebenan. Sein Hobby ist es, Kindern den Tag zu vermiesen. Er beschwert sich über die Lautstärke von Timis Sportschuhen.
- **Kevin [ID: NPC_KEVIN]:** Ein etwas älterer Junge mit Kapuzenpulli. Er schleicht verdächtig um die "Sauren Zungen" herum und wartet auf eine Ablenkung.

## Objects & Item Types

### Consumables
- **Die 1-Euro-Münze [ID: ONE_EURO, item_type: KEY]:** Timis ganzer Stolz. Absolut notwendig für den legalen Erwerb von Zuckerwaren.
- **Saure Zungen [ID: SOUR_TONGUES, item_type: CONSUMABLE]:** Kevin hat es auf sie abgesehen. Sie verleihen einen kurzen Energieschub (und ein sehr saures Gesicht).
- **Glücks-Dauerlutscher [ID: LUCKY_LOLLIPOP, item_type: CONSUMABLE]:** Ein riesiger, bunter Lutscher, der angeblich die Überredungskunst steigert.

### Tools & Items
- **Die alte Klingel [ID: SHOP_BELL, item_type: TOOL]:** Steht auf dem Tresen. Wenn man sie benutzt, reagiert Angus... manchmal etwas zu enthusiastisch.
- **Verwirrende Broschüre [ID: WEIRD_PAMPHLET, item_type: READABLE]:** Ein Zettel von Frau Schurbel über "Die Wahrheit hinter dem Marzipan".

### Wearables
- **Timis "Schnelle Schuhe" [ID: SPEEDY_SHOES, item_type: WEARABLE, wearable_slots: ["Feet"]]:** Quietschen leicht auf dem Linoleum, erhöhen aber die Fluchtgeschwindigkeit vor Herr Griesgram.

## Main Quest: Die Rettung der Sauren Zungen
1. **Herr Griesgram passieren:** Finde einen Weg, an ihm vorbeizukommen, ohne in eine 10-minütige Standpauke über "die Jugend von heute" zu geraten.
2. **Kevin stoppen:** Beobachte Kevin in der **Schund-Ecke**. Sobald er versucht, die **Sauren Zungen** einzustecken, musst du handeln.
3. **Den Deal abschließen:** Benutze die **1-Euro-Münze** bei **Angus**, um deine eigene Belohnung zu kaufen, nachdem du den Diebstahl verhindert hast.
