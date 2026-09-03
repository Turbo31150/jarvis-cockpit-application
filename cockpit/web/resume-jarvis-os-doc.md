# Résumé analytique : JARVIS OS — Document Complet de Référence Technique

**Auteur :** Franc Delmas (Turbo)
**Publié :** 14 août 2026, 23h55 | **Langue d'origine :** français (non traduit)
**Format lu :** Markdown, lecture intégrale (540 lignes, 22 139 octets)
**Domaine :** Ingénierie système Linux · Architecture de cluster LLM local · Souveraineté numérique
**Objectif du lecteur :** Référence personnelle et argumentaire commercial
**Résumé créé :** 24 août 2026, 11h00
**Qualité de la source :** Lecture intégrale du texte + **vérification empirique de 9 affirmations
contre des mesures prises le 24/08 entre 10h20 et 11h00 sur la machine décrite**

> ⚠️ Ce document est une **référence technique**, pas un livre d'argumentation. Conformément au
> cas prévu par le skill, « thèse centrale » devient **cadre conceptuel**, « idées clés » devient
> **concepts fondamentaux**, et « connexions intellectuelles » devient **prérequis et suites**.

---

## Cadre conceptuel

Le document soutient qu'une machine grand public — un portable ASUS i5-11400H à 16 Go — peut
être transformée en appliance IA souveraine performante **non pas en changeant le matériel, mais
en supprimant systématiquement chaque mécanisme d'économie d'énergie du BIOS au noyau**, couche
par couche, et que le gain cumulé de ces neuf couches (~18× en vitesse de traitement IA) rend
inutile le recours au cloud pour l'inférence et la recherche documentaire.

C'est une thèse **contestable**, et c'est ce qui la rend intéressante : elle parie que le
plafond d'une machine est administratif (des réglages bridés) plutôt que physique (dissipation
thermique, canal mémoire, bus). Les mesures du 24/08 montrent que **ce pari est gagné sur les
couches logicielles et perdu sur les couches physiques**.

---

## Concepts fondamentaux

### 1. La performance est un état à maintenir, pas un pic à atteindre

Le document traite la fréquence, le cache et la RAM comme des ressources qui doivent rester
**chaudes en permanence** : gouverneur `performance`, EPB = 0, C-States C2–C7 désactivés,
cache L3 jamais vidé, HugePages en `always`. La logique est cohérente : chaque mécanisme
d'économie d'énergie est un délai de réveil, et les délais s'additionnent.

- **Preuve avancée :** « 4 500 MHz continus vs 800–2 700 MHz stock → +462 % de fréquence effective »
- **Qualité de preuve : FAIBLE.** Vérification du 24/08 11h00 : `scaling_min_freq = 800 000 kHz`
  — soit exactement la valeur « stock » que le document affirme avoir éliminée par
  `scaling_min_freq = scaling_max_freq`. Fréquence réelle mesurée sur cpu0 : **3 788 MHz**, pas
  4 500. `min_perf_pct = 100 %`. Le verrouillage décrit n'est pas en place.
- **Localisation :** Couches 1 et 3, section 3

### 2. Le stockage et l'accès aux données sont le vrai goulot d'un système RAG

C'est le concept le plus solide du document. Il déplace l'attention du CPU vers la chaîne
SQLite : mode WAL, `mmap_size` à 10 Go, `cache_size` 64 Mo, files I/O portées de 128 à 1 024
requêtes, lecture anticipée à 8 Mo. L'idée sous-jacente — mapper les bases en RAM plutôt que
de les lire — est correcte et c'est elle qui produit les gains les plus défendables.

- **Preuve avancée :** « Search 211k Skills : 4,12 ms » · « Board OS RAG : 47 ms »
- **Qualité de preuve : FORTE — et même sous-estimée.** Vérifié le 24/08 : `skillsmp.db`
  contient **211 270 skills, au chiffre près**, et une recherche FTS5 revient en **4 ms**.
  Mieux : `board.db` répond en **5–6 ms** sur `MATCH`, soit **8× plus vite** que les 47 ms
  annoncés — alors que la base a grossi de 83 205 à **528 772 chunks**. Le document se
  sous-vend sur son point le plus fort.
- **Localisation :** Couches 6, 7 et 9

### 3. La souveraineté se construit par la cascade, pas par un modèle unique

Le document décrit une délégation par nature de tâche : résumé → petit modèle, code → gros
modèle, raisonnement → modèle spécialisé, architecture → cloud. Le cloud n'est pas banni, il
est **réservé à l'arbitrage**. C'est la doctrine la plus durable du document, et elle a
survécu à l'épreuve : le 24/08, un incident Anthropic (529 Overloaded) a détruit une
orchestration entière de 5 agents pendant que le cluster local répondait en 5 ms.

- **Preuve avancée :** tableau de cascade `lm-ask.sh` / `--big` / `--reason` / Antigravity
- **Qualité de preuve : MODÉRÉE.** La doctrine tient, la topologie est périmée. `llama3.2` et
  `deepseek-r1:7b`, annoncés servis par Ollama local, sont **ABSENTS** (mesure 24/08 : seuls
  `gemma3:4b`, `qwen2.5:7b`, `qwen3:1.7b`, `qwen2.5:0.5b` et deux embedders sont présents).
  Le nœud « M1 » du document est devenu M6, et `qwen3.5-35b` / `glm-4.7-flash` n'existent pas.
- **Localisation :** Section 5

### 4. La méthode est reproductible parce qu'elle est ordonnée

Le pipeline en 5 phases (BIOS → premier démarrage → verrouillage MSR → 9 couches noyau →
déploiement données) est présenté comme un ordre **imposé**, pas comme une liste de réglages.
C'est ce qui distingue ce document d'un recueil d'astuces : il affirme que l'ordre compte,
et il a raison — régler le noyau avant le BIOS produit des réglages qui s'écrasent au reboot.

- **Preuve avancée :** structure même du document (sections 2 et 3)
- **Qualité de preuve : MODÉRÉE.** La méthode est logique et les commandes sont exactes, mais
  aucune trace de vérification post-reboot n'est fournie. Or c'est précisément là que les
  réglages se perdent — et `scaling_min_freq = 800 MHz` mesuré aujourd'hui en est la preuve.

---

## Citations notables

1. > « Quand j'installe un système, je règle la machine à la perfection » — titre de la section 2

   *Pourquoi ça compte :* c'est le principe organisateur de tout le document, et aussi sa
   faiblesse. « À la perfection » est un objectif sans critère d'arrêt ni de vérification.
   Le document n'inclut aucune procédure de re-contrôle — d'où la dérive constatée dix jours plus tard.

2. > « Marge thermique : +40 °C de sécurité → zéro throttling » — section 4.2

   *Pourquoi ça compte :* c'est l'affirmation la plus fausse du document, et elle est fausse
   d'une manière instructive. Elle est **vraie au repos** (63 °C mesurés le 24/08 à 11h00,
   contre 61,3 °C annoncés) et **fausse en charge** : 91 à 96 °C mesurés le même jour, avec
   throttling réel à 2 394 MHz. Mesurer au repos et généraliser à la charge est le biais
   classique du benchmark maison.

3. > « Board OS : 83 205 chunks nobles de doctrine (purge de 181 447 chunks JSON bruités) » — couche 9

   *Pourquoi ça compte :* le chiffre est périmé d'un facteur **6,4** (528 772 au 24/08), mais
   la démarche — purger le bruit avant d'indexer — reste le bon réflexe. Le problème n'est pas
   la purge, c'est l'absence de date sur le chiffre.

---

## Méthodologie de l'auteur

**Mode d'argumentation dominant :** empirique auto-mesuré — le document repose presque
entièrement sur des benchmarks réalisés par l'auteur sur sa propre machine.

**Base de preuves :** mesures `sysfs`/`proc`, chronométrages SQLite, comparaisons avant/après.
Aucune source externe, aucune réplication indépendante, aucun intervalle de confiance.

**Force réelle :** la partie stockage/RAG est **vérifiable et vérifiée**. 211 270 skills au
chiffre près, 4 ms de latence FTS5 confirmés, et un board qui fait mieux que promis. Quand
l'auteur mesure des choses qu'il contrôle entièrement, il mesure juste.

**Limite significative :** le document ne distingue jamais **mesure au repos** et **mesure en
charge**. Les 61,3 °C, les 4 500 MHz stables et le « zéro throttling » décrivent une machine
qui ne travaille pas. Sous charge réelle — celle pour laquelle la machine est censée être
optimisée — la même machine monte à 96 °C et tombe à 2 394 MHz. C'est une omission structurelle,
pas une erreur de détail.

**Contrôle du biais de sélection :** présent et non traité. Chaque gain est exprimé en
pourcentage contre un « état stock » dont la méthode de mesure n'est jamais décrite
(« 12–25 Mo/s », « 150 ms », « 1 800 ms »). Un dénominateur non documenté rend tout
pourcentage invérifiable — et « +3 066 % » est précisément le genre de chiffre qui doit être
tenu à distance.

**Mise à jour des preuves depuis publication (10 jours) :**

| Affirmation du 14/08 | Mesure du 24/08 | Verdict |
|---|---|---|
| board.db : 83 205 chunks, 3,1 Go | **528 772 chunks, 4 961 Mo** | périmé ×6,4 |
| skillsmp.db : 211 270 skills | **211 270** | ✅ exact |
| Recherche 211k skills : 4,12 ms | **4 ms** | ✅ exact |
| Board OS RAG : 47 ms | **5–6 ms** (`MATCH`) | ✅ **8× mieux qu'annoncé** |
| unified_plan.db : 1,7 Go | **1 685 Mo** | ✅ exact |
| CPU verrouillé à 4 500 MHz | `scaling_min_freq` = **800 MHz**, réel **3 788 MHz** | ❌ réfuté |
| 61,3 °C, zéro throttling, +40 °C | **63 °C au repos / 91–96 °C en charge** | ❌ vrai au repos seulement |
| Ollama : gemma3:4b, llama3.2, deepseek-r1:7b | `llama3.2` **absent**, `deepseek-r1:7b` **absent** | ❌ 1 sur 3 |
| Bridges H24 (6 ports) | 5 sur 6 en écoute | ⚠️ partiel |

---

## Prérequis et suites

| Relation | Ouvrage / doctrine | Explication |
|---|---|---|
| S'appuie sur | Doctrine `CAHIER-DES-CHARGES-NOYAU-OMEGA` | Le cycle en 10 étapes et les 6 interdits (« chiffre sans date ») sont la réponse directe aux faiblesses de ce document |
| Répond à | La dépendance au cloud IA | Le document est une réfutation pratique de « il faut des GPU datacenter pour faire de l'IA utile » |
| Renforcé par | Mesures du 24/08 sur le stockage | Le volet SQLite/FTS5 sort **grandi** de la vérification, pas diminué |
| Contredit par | La thermique de la machine elle-même | 91–96 °C avec throttling à 2 394 MHz. Le CLAUDE.md le reconnaît : « le levier restant est physique — dépoussiérage + pâte thermique » |
| Contredit par | Le bus USB partagé | L'adaptateur réseau ET le SSD M1 sont sur le **même bus 3 à 480 Mb/s** ; les bus 2 (10 Gb/s) et 4 (20 Gb/s) sont vides. Aucun réglage noyau ne franchit un plafond de bus |

**Ordre de lecture recommandé : fondamental.** À lire avant tout document JARVIS applicatif —
mais **après** avoir intégré la règle « tout chiffre porte sa date », sans quoi on hérite de
ses valeurs périmées.

---

## Notes d'application

**Contexte :** exploitation quotidienne du cluster JARVIS et argumentaire commercial ALKYMIA.

1. **Sous-estimation du RAG → argumentaire commercial → corriger la plaquette vers le haut**
   La plaquette annonce 47 ms là où la mesure donne 5–6 ms sur une base 6,4× plus grosse.
   C'est un argument de vente qu'on laisse sur la table.
   *Échéance :* avant le prochain envoi de `PLAQUETTE_JARVIS_OS_FRANCK_v3.pdf`.

2. **Distinction repos/charge → tout benchmark futur → mesurer sous charge soutenue, jamais au repos**
   Toute mesure thermique ou de fréquence doit être prise pendant une charge réelle d'au moins
   10 minutes. Le 24/08 l'a montré : 63 °C au repos, 96 °C en charge, sur la même machine à
   40 minutes d'intervalle.
   *Échéance :* immédiat — règle à appliquer dès le prochain relevé.

3. **`scaling_min_freq` à 800 MHz → réglage machine → décider si on rétablit le verrouillage**
   Le document affirme un verrouillage qui n'est pas en place. Deux lectures possibles : soit
   il a été perdu à un reboot, soit il a été retiré volontairement pour le thermique. Il faut
   trancher, pas laisser l'écart.
   *Échéance :* sous 7 jours.

4. **Chiffres sans date → tous les documents → dater chaque valeur à la ligne**
   Les six affirmations réfutées le sont toutes pour la même raison : aucune ne porte sa date.
   Le `CAHIER-DES-CHARGES` l'a déjà érigé en interdit ; ce document est la démonstration du pourquoi.
   *Échéance :* à appliquer à la prochaine révision de la plaquette et du CLAUDE.md.

**Où je suis en désaccord :** le document présente les neuf couches comme un ensemble homogène
produisant « ~18× ». La vérification montre deux régimes très différents : les couches
**données** (6, 7, 9) tiennent et dépassent leurs promesses, les couches **silicium** (1, 2, 3)
ne tiennent pas — elles butent sur une dissipation thermique que rien de logiciel ne franchit.
Présenter les deux sous un chiffre unique masque le fait que la moitié de la valeur est réelle
et durable, et l'autre moitié provisoire.

---

## Verdict

La contribution durable de ce document n'est pas le « ×18 » : c'est la **démonstration
vérifiable qu'un RAG local sur un demi-million de chunks répond en 5 millisecondes sur du
matériel grand public**. C'est ça qui se vend et qui tient dix jours plus tard. Le volet
silicium — fréquences verrouillées, températures maîtrisées, zéro throttling — ne survit pas
à la mesure sous charge, et le maintenir dans l'argumentaire expose à une réfutation
immédiate par n'importe quel prospect qui lance `sensors` pendant une démo.

À lire par quiconque veut monter une appliance IA souveraine, **en tenant les chiffres de
stockage pour acquis et les chiffres thermiques pour caducs**.

---

## Auto-contrôle

À répondre sans relire le document :

- [ ] Énoncer le cadre conceptuel en une phrase
- [ ] Nommer 3 concepts fondamentaux
- [ ] Citer une affirmation vérifiée et une affirmation réfutée, avec son chiffre
- [ ] Nommer la faiblesse méthodologique structurelle

**Lacunes à surveiller :** si la distinction repos/charge ne vient pas spontanément, relire la
section Méthodologie — c'est le seul défaut qui invalide plusieurs affirmations d'un coup.

---

## Calendrier de révision espacée

| Révision | Quand | Objet |
|---|---|---|
| 1 | 25 août | Relire en entier · le cadre conceptuel revient-il de mémoire ? |
| 2 | 29 août | Masquer les concepts fondamentaux · la plaquette a-t-elle été corrigée ? |
| 3 | 10 septembre | Masquer les notes d'application · `scaling_min_freq` a-t-il été tranché ? |
| 4 | 10 octobre | Passe complète · re-mesurer les 9 affirmations et dater le nouveau relevé |

---

*Résumé produit le 2026-08-24 à 11h00. Les 9 vérifications empiriques ont été exécutées sur
`pamerys-m4` entre 10h20 et 11h00 ; chaque chiffre de la colonne « mesure » est reproductible
par la commande citée dans la mémoire `MESURES-2026-08-24-11h-vectoriseur-et-memoire`.*
