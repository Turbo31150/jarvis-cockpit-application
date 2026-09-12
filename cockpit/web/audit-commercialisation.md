# Audit de commercialisation — JARVIS OS (cockpit)

## 1. Résumé exécutif

JARVIS OS est un **cockpit web souverain d'orchestration IA auto-hébergé**, développé par un contributeur unique sur une machine unique (rig « mining » : Intel i5-3450 sans AVX2, 31 Go RAM, RTX 2060 + RTX 3080). Il pilote un poste Linux et un cluster GPU maison, combine un **conseil d'experts local** (`board.db` : 7,4 Go, 1,07 M chunks, 48 experts/14 domaines, 14 k citations tracées) interrogeant un corpus RAG à coût-token nul, et une **« Table Ronde »** qui agrège les IA web (Gemini/ChatGPT/Perplexity) via Chrome DevTools Protocol.

**Verdict de maturité : prototype avancé mono-utilisateur, pas un produit.** La base de code est substantielle (346 fichiers Python, ~143 k lignes, 320 fichiers de tests), mais le versioning est immature (**1 commit git**, 20 fichiers non commités), il n'y a **aucun utilisateur externe ni revenu**, la sécurité est artisanale (`.env` en clair, cockpit sans auth), et le README survend (« 10521 skills » vs 468 réels).

**Potentiel commercial réaliste : étroit mais réel.** Le seul récit vendable et finançable n'est pas « OS IA complet » mais **« appliance RAG souveraine 0-token à réponses citées et auditables »**. Le moat défendable tient en deux points : le corpus `board.db` curé (donnée + annotation, coûteux à répliquer) et la discipline *« réponse sans citation = rejetée, vérifiable en SQL »*. Le reste (700 outils MCP, orchestration OMEGA, cluster GPU, Table Ronde) est impressionnant en volume mais **rattrapable**, et la Table Ronde constitue un **risque juridique/TOS** à sortir du cœur produit. Cible immédiate : **cabinets régulés mono-site** (avocat, comptable, médecin) où la souveraineté est une contrainte légale.

---

## 2. Le produit JARVIS OS

### Définition
Cockpit web souverain qui orchestre un poste Linux et un cluster GPU maison (voix, CLI, API REST, dashboards), apprend de chaque interaction, et répond avec des sources citées à coût d'inférence local ~0.

### Capacités principales (preuves)

| Capacité | Preuve / chemin |
|---|---|
| **Cockpit web / dashboards** | `cockpit/serveur.py` (42 Ko, ThreadingHTTPServer), ports 8600/8610/8088 |
| **Board — conseil d'experts local** | `board/board.py` + `board.db` : **7,4 Go, 1 072 270 chunks, 311 175 sources, 48 experts / 14 domaines, 14 147 citations, 4 668 réponses** ; règle SQL vérifiable (vue `answers_sans_citation`) |
| **RAG vivant sémantique** | `omega/rag/live_rag.py` + `bin/jarvis-rag` ; **170 568 embeddings** nomic-768d (~16 % du corpus vectorisé) |
| **Table Ronde CDP** | `omega/rag/table_ronde.py` + `bin/jarvis-tr` ; profils Chrome 9223/9224, extraction DOM → `board.db` |
| **~700 outils MCP** | `src/mcp_server.py` (6 710 lignes), `src/tools.py` (204 handlers) ; famille `mcp__jarvis-mcp__*` |
| **Orchestration OMEGA** | `omega/` : domino-continu tri-moteur, légion tmux, journée (timers systemd autonomes) |
| **Outillage** | `bin/` (jarvis-rag, jarvis-tr, omega-ctl…), `scripts/` (486), catalogue skills local (468) |

### Architecture
Python bout-en-bout. Inférence locale (Ollama dual-GPU 2060+3080 ; LM Studio en CPU/runtime seulement, AVX2 requis pour le GPU → inutilisable). RAG lexical FTS5 + embeddings nomic-768d, arbitrage par LLM local (qwen3-8b). Serveur MCP first-class (204 handlers exposés). Le tout **cloué à cette machine** (chemins `/home/turbo`, symlink MOISSON, LM Studio local) = SPOF matériel et non portable.

---

## 3. Différenciateurs clés — moat réel vs rattrapable

### Vrai moat (défendable)
1. **Le corpus `board.db`** : 1,07 M chunks curés en 48 experts/14 domaines avec 14 k citations tracées. C'est de la **donnée + de l'annotation**, pas du code — non réplicable par un `git clone`. *Réserve honnête* : la provenance/licence des 311 k sources est inconnue (risque droit d'auteur à auditer avant d'en faire un argument).
2. **Discipline « réponse sans citation = rejetée », auditable en SQL** : garantie anti-hallucination *vérifiable*, rare et vendable en environnement régulé. *Réserve honnête* : « il y a une citation » ≠ « la citation soutient la réponse » — sans métrique de fidélité (faithfulness) mesurée, c'est de l'anti-hallucination cosmétique.
3. **Souveraineté 0-token réellement implémentée** bout-en-bout (inférence + RAG locaux). La promesse « rien ne sort » est vraie — **sauf** pour la Table Ronde (voir §10).

### Rattrapable (commodité, à présenter comme bonus)
- **~700 outils MCP** : beaucoup de wrappers, et certains tombent en « internal error » (dérive handler↔module). Le nombre n'est pas un avantage durable.
- **Cluster GPU maison + orchestration OMEGA** : impressionnant mais reproductible (c'est du code). Et ce n'est pas un « cluster » (machine unique, carte mère grand public) : un **poste bi-GPU**.
- **Table Ronde CDP** : astucieuse mais fragile (sélecteurs DOM cassants, sessions expirantes) et à risque TOS.

---

## 4. Paysage concurrentiel

| Critère | **JARVIS OS** | **OpenClaw** | **Claude Code / Cursor** | **Frameworks (CrewAI/LangGraph)** | **Cockpits OSS (Open WebUI/LibreChat)** |
|---|---|---|---|---|---|
| **Cible** | Power-user / cabinet régulé mono-site | Particulier / power-user solo | Développeurs | Devs → SaaS/entreprise | Équipes chat local |
| **Déploiement** | Auto-hébergé, cloué à 1 machine | Auto-hébergé, npm, apps natives | Cloud SaaS | Librairie/SDK à intégrer | Auto-hébergé, Docker |
| **Coût / tokens** | ~0 (inférence locale) | Local possible **mais sponsors cloud** | 20–200 $/siège/mois | Au token cloud (63–171 $/1000 runs) | Façade → surtout API cloud |
| **Souveraineté** | Forte (hors Table Ronde) | Forte, mais dépend de modèles cloud | Nulle (code chez tiers) | Faible (inférence cloud) | Variable |
| **Maturité** | Prototype mono-commit | **Foundation 501(c)(3), MIT, 346k★, releases signées** | Production, support pro | Production (LangGraph leader) | Open WebUI ~147k★, RBAC multi-user |
| **Moat** | Corpus curé + citation auditable | Communauté + 23 canaux + apps mobiles | Qualité modèle frontier | Écosystème/adoption | Adoption + RBAC |

**Lecture** : OpenClaw est le cousin le plus proche (même ADN local/souverain/mono-user) et écrase sur communauté, packaging et connectivité canaux — mais **refuse par doctrine** l'orchestration multi-agents hiérarchique (VISION.md « What We Will Not Merge ») et n'a ni board d'experts ni multi-GPU. Les cockpits OSS ont déjà le RBAC multi-user que JARVIS n'a pas. Aucun concurrent n'occupe exactement le créneau « appliance RAG à citations auditables ».

---

## 5. SWOT

| **Forces** | **Faiblesses** |
|---|---|
| Corpus `board.db` curé (vrai moat data) | Mono-utilisateur, pas de multi-tenant ni RBAC |
| Citation obligatoire auditable en SQL | Sécurité artisanale (`.env` clair, cockpit sans auth) |
| Souveraineté 0-token réelle | SPOF matériel + hardware ancien (i5 sans AVX2) |
| Profondeur RAG + orchestration OMEGA | Dérive handler↔module MCP (outils en « internal error ») |
| Base de code substantielle + tests | Gouvernance immature (1 commit), README survendeur |
| | RAG vivant à ~16 % vectorisé ; qualité modèle local plafonnée |

| **Opportunités** | **Menaces** |
|---|---|
| Data-residency / RGPD en hausse (2026) | OpenClaw ajoute un board → moat #2/#3 s'évapore |
| Coûts tokens cloud qui explosent à l'échelle | RAG déjà commoditisé (Open WebUI, LibreChat, Dify) |
| Durcissement licence Open WebUI (fenêtre MIT) | Risque juridique Table Ronde (TOS) + provenance board.db |
| Convergence marché vers orchestration multi-agents | Concurrence cloud gagne sur qualité modèle et robustesse |
| Intégrer l'écosystème OpenClaw (skills, ClawHub) | Risque bus (équipe = 1 personne) |

---

## 6. Voie 1 — Vente à des clients

### Segmentation (priorisée)

| Segment | Verdict |
|---|---|
| **A. Cabinets régulés mono-site** (avocat, comptable, médecin, notaire) | **CIBLE #1** — mono-user OK, souveraineté = argument légal (secret pro, RGPD, HDS) |
| B. PME/ETI souveraineté-sensibles | Cible #2 différée — bloquée par absence multi-tenant/auth/SLA |
| C. Intégrateurs / MSP locaux | **Canal** (marque blanche), pas segment final |
| D. Self-hosters / prosumers | Communauté, faible willingness-to-pay (OpenClaw MIT gratuit juste à côté) |
| E. Grand public | À écarter (SPOF, DX immature) |

### Offre et proposition de valeur
On vend le **problème résolu**, pas le code nu (l'installation exposerait toute la dette). Format = **appliance clé-en-main « JARVIS Box »** : mini-tour préconfigurée (1 GPU moderne 12–16 Go, pas le rig i5-3450 qui reste banc de dev), cockpit + `board.db` préchargé, setup + formation on-site, support annuel.

**Pitch** : *« Votre IA qui répond avec des sources citées et vérifiables, 100 % dans vos murs, zéro donnée qui sort, zéro abonnement au token — auditable pour votre DPO. »*

### Pricing indicatif

| Ligne | Prix | Ancrage |
|---|---|---|
| Appliance JARVIS Box (matériel + install + corpus) | **4 500–7 000 €** one-shot | Matériel ~1 200–1 800 € ; reste = intégration + corpus |
| Support & mises à jour | **1 800–3 000 €/an** | vs 125 $/user/mois Claude Code équipe |
| Corpus métier sur-mesure | **1 500–4 000 €** / domaine | Valorise le moat (annotation/citations) |
| Option Table Ronde web | **best-effort explicite** | Jamais vendue comme cœur ni SLA |

**Cible année 1** : 8–15 appliances = 40–100 k€ one-shot + 15–35 k€/an récurrent. Point mort atteignable en solo/duo.

### GTM
1. **Prescription métier** (ordres, DPO indépendants, éditeurs logiciels métier) — le RGPD est le déclencheur d'achat.
2. **Intégrateurs/MSP en marque blanche** — meilleur levier de scale.
3. **Contenu de preuve** : démo « réponse citée + audit SQL du zéro-hallucination », pas de démo « 700 outils » (non crédible).
4. **Événements souveraineté/RGPD régionaux**, pas les salons dev (où OpenClaw gratuit gagne).

**Obstacle de vente n°1** : le SPOF matériel est rédhibitoire en cabinet médical → offrir une **2ᵉ box de secours** ou un plan de restauration (backup `board.db`) est obligatoire.

---

## 7. Voie 2 — Pitch investisseurs

**Stade : pré-seed / prototype de fondateur.** 1 contributeur, 1 machine, 1 commit, 0 utilisateur, 0 revenu. Un investisseur financerait **l'équipe et le pivot vers l'appliance RAG**, pas l'« OS IA » actuel.

**Angle** : ne pas pitcher « OS IA 700 outils ». Pitcher **« appliance RAG souveraine, 0-token, à réponses citées et auditables »**. Phrase testable : *« Chaque réponse cite ses sources ou elle est rejetée — vérifiable en SQL. Rien ne sort de votre infra. »*

**Marché (ordres de grandeur à sourcer avant term sheet)** :
- **TAM** : IA d'entreprise + souveraine, dizaines de Md$ (trop large pour être utile).
- **SAM** : RAG/assistants self-hosted on-prem pour organisations à contrainte de résidence des données (UE/RGPD) — quelques Md$, croissance rapide.
- **SOM 24 mois** : PME/ETI européennes régulées déployant une appliance à 10–20 k€ ; quelques dizaines de clients = ARR à 6 chiffres. Modeste et honnête, pas « 100 Md$ ».

**Timing (pourquoi maintenant)** : coûts tokens cloud en hausse ; souveraineté/data-residency montée en 2026 ; signaux marché (durcissement licence Open WebUI, convergence Windsurf→orchestration d'agents).

**Risques majeurs à ne pas masquer** : équipe = 1 personne (risque bus) ; SPOF + hardware ancien ; dépendance Table Ronde (TOS) ; concurrence OpenClaw/Open WebUI ; sécurité artisanale ; communication non fiable (README faux).

**Ce qu'il faut prouver pour lever (par ordre)** :
1. **1 client payant régulé** en pilote on-prem (même 5 k€) — la seule preuve qui compte.
2. **Découpler du hardware** (installeur reproductible, démo sur machine tierce).
3. **Métriques RAG dures** : latence p50/p95, taux de citation, **taux de fidélité mesuré**, couverture d'embeddings (aujourd'hui ~16 %).
4. **Auth + multi-tenant minimal**.
5. **2ᵉ personne** (tuer le risque bus).
6. **Cadrer/sortir la Table Ronde**.

---

## 8. Voie 3 — Positionnement open-source vs OpenClaw

**Constat** : JARVIS n'est pas open-source (badge « Privée », mono-commit). Face à OpenClaw (MIT/Foundation), Open WebUI (~147k★) et LibreChat (MIT), il part de zéro sur **communauté, packaging, gouvernance** — un retard structurel.

**Stratégie recommandée : open-core, pas tout-ouvert.**
- **Ouvrir (MIT) le moteur** : cockpit, runtime MCP, orchestration OMEGA, connecteurs Ollama — pour exister dans la conversation OSS.
- **Garder fermé/premium le corpus `board.db`** (ou seed ouvert + corpus complet sous licence data). Le moat étant la donnée, l'open-core est naturel : on ouvre le code, on protège/monétise la donnée.
- **Divergence, pas fork.** Forker OpenClaw (TS/Node) imposerait de réécrire tout JARVIS (Python) — coût prohibitif. Bonne relation : **consommateur d'écosystème** (importer ses skills, publier sur ClawHub, se brancher via `mcporter`). On capte sa communauté sans porter sa dette.
- **Message étroit** : « appliance RAG souveraine à citations auditables », pas « OS IA complet ».

**Risque de commoditisation** : élevé et proche sur le RAG simple (déjà commoditisé). Seule la **paire corpus-curé + citation-auditable** y échappe encore. Menace frontale = OpenClaw : s'il ajoute un board d'experts, seul l'avantage #1 (le corpus) tient dans la durée.

---

## 9. Cadrage stratégique interne — dette priorisée

**P0 — bloquants absolus (ne pas vendre sans) :**

| # | Chantier | Effort |
|---|---|---|
| 1 | **Fiabilité MCP** : réconcilier dérive handler↔module (outils en « internal error »), tests d'intégration sur les 204 handlers, CI qui casse au moindre échec | 3–4 sem. |
| 2 | **Sécurité/secrets** : vault (age/sops), auth/RBAC sur le cockpit (ports 8600/8610/8088), durcissement | 2–3 sem. |
| 3 | **Multi-user minimal** OU verrouiller le positionnement « appliance mono-poste » et **ne pas promettre** le multi-tenant | 6–10 sem. (ou décision produit) |

**P1 — importants (avant montée en charge) :**
4. **Packaging portable** : découpler des chemins figés `/home/turbo`, installeur reproductible (étalon DX : wizard `openclaw onboard`) — 3–4 sem.
5. **SPOF matériel** : assumer (appliance) ou documenter un déploiement redondé.
6. **RAG vivant** : finir la vectorisation (~16 % → cible haute) ou ne pas survendre le sémantique.
7. **Gouvernance code** : historique git réel, **aligner le README sur la réalité** (crédibilité en due diligence).

---

## 10. Risques rédhibitoires

1. **Juridique — Table Ronde (CDP des LLM web)** : le pilotage automatisé de comptes Gemini/ChatGPT/Perplexity via CDP est une **violation directe des TOS** (usage automatisé non autorisé, contournement d'accès). Mettre cela au cœur d'une offre = risque de mise en demeure, coupure de comptes, exposition contractuelle si un client s'en sert. Contredit aussi frontalement le discours « souverain 0-token ». → **Décision : sortir la Table Ronde du cœur produit**, la garder comme outil interne « best-effort » non vendu, ou la remplacer par des API officielles assumées. **Ne jamais la contractualiser.**
2. **Provenance/licence de `board.db`** : si les 311 k sources sont du contenu protégé scrappé, le seul moat devient un passif juridique. → Auditer la provenance avant d'en faire un argument.
3. **Sécurité/conformité** : un incident de fuite chez un cabinet régulé (secret pro/RGPD/HDS) tue la réputation et engage la responsabilité. `.env` clair + cockpit sans auth = l'inverse de ce qu'on vend.
4. **SPOF matériel** : panne disque/GPU chez un client santé sans redondance = rupture critique, contrat perdu.
5. **Crédibilité** : README faux (« 10521 skills » vs 468) + mono-commit → la première due diligence révèle l'écart réalité/discours et brûle la confiance de façon irréversible.

---

## 11. Recommandations priorisées — roadmap 30/90/180 jours

### 30 jours (crédibilité + décisions à coût nul)
- **Sortir la Table Ronde du périmètre commercial** (décision immédiate, coût ~0).
- **Aligner le README sur la réalité** et créer un historique git réel.
- **Trancher le positionnement** : « appliance mono-poste » (assumé) vs multi-tenant (chantier lourd).
- Démarrer P0-1 (fiabilité MCP) et P0-2 (auth cockpit + vault) en parallèle.

### 90 jours (produit vendable minimal)
- **Solder P0** : MCP fiable sous CI, auth/RBAC + secrets sécurisés.
- **Packaging portable** : installeur découplé du hardware, démo sur machine tierce.
- **Métriques RAG dures** : publier latence p50/p95, taux de citation et **taux de fidélité mesuré**, plan pour monter la couverture d'embeddings.
- Construire le prototype **JARVIS Box** (matériel cible ≠ rig i5).

### 180 jours (première traction)
- **1 client pilote régulé** on-prem (même 5 k€) avec 2ᵉ box de secours.
- **Auditer la provenance de `board.db`** (sécuriser le moat juridiquement).
- **Recruter une 2ᵉ personne** (tuer le risque bus).
- Amorcer la **stratégie open-core** (ouvrir le moteur MIT, protéger le corpus) et se brancher sur l'écosystème OpenClaw (skills/ClawHub).

**Règle d'or : ne rien vendre tant que P0 (1-2-3) n'est pas soldé, et ne jamais contractualiser la Table Ronde.**

---

## 12. Verdict honnête

JARVIS OS est un **actif technique réel mais survendu**. « OS IA souverain à cluster GPU et 700 outils » est un récit invérifiable et rattrapable : ce n'est ni un OS (surcouche Python sur Linux), ni un cluster (poste bi-GPU unique), et le volume d'outils masque une dette (outils en « internal error »). Le **seul récit défendable, vendable et finançable est étroit** : **une appliance RAG souveraine à réponses citées et auditables**, portée par le moat data (`board.db`) et la discipline de citation.

Mais ce récit exige d'abord de **solder la dette P0** (fiabilité MCP, sécurité/auth), de **dire la vérité sur les chiffres** (README), de **sortir la Table Ronde** du cœur (risque TOS), d'**auditer la provenance du corpus**, et de **mesurer la fidélité** (pas seulement la présence de citations). En l'état — mono-machine, mono-dev, dépendances TOS, sécurité artisanale, chiffres survendus — **un DSI sérieux ne signe pas et un VC sérieux ne finance que l'équipe et le pivot, pas le produit actuel.**

La bonne nouvelle : le pivot est clair, la fenêtre de marché (souveraineté, coûts tokens, durcissement licences OSS) est ouverte, et le moat data est authentique. Le risque n'est pas technique — c'est de rester un projet mono-commit/mono-machine pendant que les cousins MIT capitalisent communauté et packaging.