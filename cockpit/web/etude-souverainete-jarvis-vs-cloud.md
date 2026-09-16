# Etude comparative — Assistant IA souverain local (JARVIS OS) versus assistants IA cloud (septembre 2026)

*v2 — revisee le 2026-09-16 apres revue editeur (MAJOR REVISION) / devil's advocate (REVISE) / ethique (CONDITIONAL).*

## 1. Resume executif

JARVIS OS est un assistant IA opere en local, dont l inference et la synthese vocale tournent sur le materiel de l organisation (LM Studio + Kokoro, 22 Go de VRAM sur 2 GPU — compteur interne, voir section 2b), avec un socle documentaire de 312 976 documents-sources fragmentes en 1 078 513 chunks vectorises (mesures en direct sur la base `board.db`). Son argument central n est pas d etre le seul systeme capable de tourner en local — cette pretention serait fausse, car Gemini via Google Distributed Cloud air-gapped, Mistral Le Chat Enterprise self-hosted et les capacites Windows on-device Phi Silica offrent aussi des modes locaux ou hors-ligne. Deux differenciateurs restent toutefois solidement defendables : (1) dans cette configuration locale, et sous reserve que les noeuds cloud optionnels (gpt-oss-cloud, devstral, glm) soient desactives, aucune donnee ne sort du perimetre, donc rien ne peut servir a entrainer un modele tiers ni etre relu par un humain externe ; (2) la conformite UE (RGPD, NIS2, reglement IA) est facilitee car rien ne franchit de frontiere et tout est journalise. La comparaison de cout doit rester honnete : le local n est pas gratuit (CAPEX GPU, electricite, maintenance), mais son cout marginal par requete tend vers zero, la ou le cloud facture au token et/ou au siege. Ce rapport signale explicitement les verdicts partiellement confirmes ou refutes issus de la verification adversariale, et distingue les metriques auditables des compteurs internes non audites.

## 2. Metriques de l instance JARVIS

Il faut distinguer deux categories de chiffres, de niveaux de preuve tres differents.

### 2a. Mesure en direct sur board.db (auditable)

Les chiffres suivants proviennent de comptes SQL en lecture seule executes en direct sur la base `board.db` de l instance, le 2026-09-16. Ils sont reproductibles par toute personne disposant d un acces lecture a la base.

| Metrique | Valeur mesuree |
|---|---|
| Experts | 52 |
| Domaines couverts | 18 |
| Documents-sources distincts | 312 976 |
| Chunks (fragments) | 1 078 513 |
| Taux de vectorisation (768D) | 99,7 % |

Precisions terminologiques (voir aussi section 8, uniformisation) : le socle documentaire correspond a environ 313 000 documents-sources, fragmentes en environ 1,08 million de chunks. Il ne faut jamais ecrire « plus d un million de documents » — ce serait confondre chunks et documents-sources. Le nombre d experts est 52.

### 2b. Compteurs systeme internes (mesures en interne, NON audites par un tiers)

Les chiffres suivants ne sont PAS presents dans `board.db`. Ce sont des compteurs remontes par le systeme lui-meme ; ils ne sont ni reproductibles par une requete simple sur la base RAG, ni audites par un tiers independant. Ils ne doivent jamais etre etiquetes « verifie ».

| Compteur interne | Valeur remontee |
|---|---|
| Outils MCP | 653 |
| Skills au catalogue | 211 270 |
| VRAM utilisee | 22 Go sur 2 GPU |
| Tokens API factures | 0 (inference locale) |
| Journal d audit | append-only |

Note methodologique : avant tout usage commercial, il est necessaire de DEFINIR operationnellement les termes « skill » et « expert ». Un compteur de 211 270 skills n a de sens que si l on precise ce qu est une unite de skill (fichier ? handler ? entree de catalogue ? variante ?) ; de meme, « expert » doit etre defini (agent ? profil de routage ? domaine ?). Sans definition operationnelle publiee, ces nombres restent des indicateurs internes, non des faits auditables. « 0 token API facture » est vrai pour cette configuration de demonstration ou l inference et la voix tournent en local ; au niveau systeme, la doctrine JARVIS prevoit des noeuds cloud optionnels (gpt-oss-cloud, devstral, glm) qui, s ils sont actives, generent des appels externes.

## 3. Tableau comparatif nuance

Ce tableau signale honnetement les options on-premises et hors-ligne des concurrents cloud, afin de ne pas surestimer l ecart.

| Dimension | JARVIS (local) | Concurrents cloud (avec leurs options on-prem / offline) |
|---|---|---|
| Lieu d inference | Sur le materiel de l organisation (LM Studio + Kokoro) | Cloud par defaut ; mais on-prem possible : Gemini sur GDC air-gapped (GA), Mistral Le Chat self-hosted, capacites Windows on-device (Phi Silica) |
| Mode hors-ligne | Oui, natif | Oui pour certains : Gemini sur GDC air-gapped (deconnecte d internet), Phi Silica sur NPU sans connexion. Assistants de marque grand public (ChatGPT, Copilot M365, Gemini Apps) : connexion requise |
| Sortie des donnees | Aucune dans cette configuration locale, si les noeuds cloud optionnels sont desactives | Depend de l offre : entreprise avec DPA = pas d entrainement par defaut ; grand public/gratuit = entrainement et relecture humaine possibles |
| Citations des sources | Oui, sources locales | Oui aussi : Perplexity par defaut, Gemini/Copilot en mode grounded/connecte. La citation n est donc PAS un differenciateur exclusif |
| Cout | CAPEX GPU + electricite + maintenance ; cout marginal par requete proche de zero | OPEX : API au token (par million de tokens) et/ou abonnement par siege ; on-prem entreprise = cout fixe negocie |
| Conformite UE | Facilitee : rien ne franchit de frontiere, tout journalise | Possible mais exige diligence contractuelle ; risque residuel de sous-traitance hors UE et exposition au CLOUD Act, attenue par les offres de cloud souverain UE (SecNumCloud, Bleu, S3NS) |
| Catalogue / outils | 52 experts, 18 domaines, ~313 k documents-sources (auditable) ; 653 outils MCP et 211 270 skills (compteurs internes non audites) | Ecosystemes proprietaires larges, mis a jour en continu par le fournisseur |

## 4. Les deux differenciateurs reellement defendables

### 4.1 Non-exfiltration dans la configuration locale : aucune donnee ne sort du perimetre

Dans cette configuration locale, et sous reserve que les noeuds cloud optionnels (gpt-oss-cloud, devstral, glm) soient desactives, aucune donnee ne sort du perimetre : il n existe alors aucun canal par lequel les prompts ou les documents pourraient alimenter l entrainement d un modele externe ou etre soumis a une relecture humaine tierce.

Ce point est d autant plus pertinent que la verification confirme que, chez les fournisseurs cloud, les offres grand public et gratuites peuvent servir a entrainer les modeles et/ou etre relues par des humains, meme si les offres entreprise s en abstiennent par defaut. Chez Anthropic, la mise a jour des conditions grand public introduit un mecanisme d opt-out active par defaut sur les comptes Free, Pro et Max (donc pas un consentement explicite prealable), les usages commerciaux et entreprise en etant exclus (Anthropic, 2025a). Cote OpenAI, la politique entreprise precise que les donnees des clients API et entreprise ne servent pas par defaut a entrainer les modeles (OpenAI, 2025). Cote Google, l aide Gemini decrit le traitement des donnees et les possibilites de relecture humaine pour les usages grand public (Google, s. d.-c). Cote Microsoft, la documentation Enterprise Data Protection precise que, dans Microsoft 365 Copilot, les prompts, reponses et donnees Microsoft Graph ne servent pas a entrainer les modeles de fondation (Microsoft, s. d.-b). L avantage JARVIS n est donc pas que « eux entrainent et pas nous » de facon generale, mais que l abstention cloud repose sur des conditions contractuelles et une configuration correcte du compte, tandis que chez JARVIS, en configuration locale, elle decoule de l architecture elle-meme.

### 4.2 Conformite UE facilitee (RGPD / NIS2 / reglement IA)

Parce que rien ne franchit de frontiere dans la configuration locale et que toutes les operations sont tracees dans un journal d audit append-only, la demonstration de conformite RGPD, NIS2 et reglement IA de l UE est facilitee : la localisation des traitements est maitrisee, la tracabilite est native, et il n y a pas de transfert international a documenter.

A l inverse, un service cloud, meme affichant une residence des donnees europeenne, conserve un risque residuel d exposition au CLOUD Act americain si le fournisseur ou l un de ses sous-traitants releve d une juridiction americaine, et peut recourir a de la sous-traitance hors UE. Ce risque n est pas « ecarte » mais reduit ; il l est aussi cote cloud par les offres de cloud souverain de l UE (SecNumCloud en France, Bleu, S3NS), qui isolent l exploitation d une juridiction etrangere. L avantage propre de JARVIS n est donc pas l exclusivite de la souverainete, mais la localite totale du traitement combinee au journal d audit : la souverainete y est structurelle plutot que contractuelle. C est un argument de gouvernance et de reduction du risque juridique, pas une affirmation d illegalite des solutions cloud.

## 5. Cadrage honnete du cout (TCO local vs OPEX par token)

Il ne faut pas presenter JARVIS comme « gratuit ». Le « 0 token API facture » signifie seulement qu il n y a pas de facturation a l usage aupres d un fournisseur externe. Le cout total de possession (TCO) local comprend le CAPEX materiel (les GPU, ici 2 GPU, et l infrastructure serveur) et l OPEX local (electricite, refroidissement, maintenance, mises a jour des modeles et competences internes).

Cote cloud, la verification confirme la coexistence de deux modeles de facturation. Tous les tarifs et noms de modeles ci-dessous sont des ordres de grandeur indicatifs, a reverifier sur la page tarifaire officielle a la date du devis ; ils evoluent frequemment et certains sont promotionnels.

- API a l usage, par million de tokens : ordres de grandeur observes de l ordre de 0,10 $ a 50 $ par million de tokens selon le modele et le sens (entree/sortie). Les noms de modeles et paliers evoques (par exemple des generations « Sonnet 5 », « Opus 5 » cote Anthropic, « GPT-5.6 » cote OpenAI, « Gemini Flash / Pro » cote Google) sont indicatifs et a revalider a la date du devis sur les pages tarifaires officielles (Anthropic, s. d.-b ; Google, s. d.-a ; OpenAI, s. d.).
- Abonnement par siege : ordres de grandeur observes de l ordre de 15 $ a 30 $ par utilisateur et par mois pour les offres grand public et equipe (par exemple Microsoft 365 Copilot en add-on necessitant une licence M365 existante, les offres equipe/pro d Anthropic, Mistral, ChatGPT). A reverifier a la date du devis ; le tarif ChatGPT Enterprise par siege n est pas publie (devis sur mesure).

Nuances a assumer : ces deux modes cohabitent et ne sont pas exclusifs ; certaines offres entreprise combinent « siege + usage aux tarifs API » ; plusieurs tarifs API sont promotionnels et temporaires, et des hausses annoncees (par exemple a horizon 2027) restent des ordres de grandeur indicatifs a revalider. Enfin, les fournisseurs cloud proposent aussi de l on-premises a cout fixe negocie, ce qui rapproche leur structure de couts de celle d un deploiement local dans certains scenarios.

### 5.1 Exemple chiffre illustratif (a ajuster)

L exemple suivant est purement illustratif : ce sont des hypotheses a adapter au cas reel, aux prix locaux et au devis fournisseur du jour. Il vise seulement a montrer un ordre de grandeur de seuil de rentabilite, pas un chiffre de reference.

Hypotheses cote local. CAPEX ~ 2 GPU + station de travail, disons de l ordre de 8 000 a 12 000 € amortis sur 3 ans, soit environ 220 a 335 € par mois d amortissement. Electricite : une consommation en charge partielle de l ordre de 250 a 400 W, disons 8 heures par jour ouvre, donne environ 250 × 8 × 22 = ~44 kWh/mois a ~400 × 8 × 22 = ~70 kWh/mois ; a un prix indicatif de ~0,20 €/kWh, cela represente environ 9 a 14 € par mois d electricite (a majorer pour le refroidissement). En arrondissant et en ajoutant une part de maintenance, on obtient un cout local de l ordre de 250 a 400 € par mois, dominé par l amortissement du CAPEX.

Hypotheses cote cloud. Pour une petite equipe, N sieges a ~20 a 30 $/mois. Une equipe de 10 utilisateurs represente donc de l ordre de 200 a 300 $/mois (environ 185 a 280 €/mois aux ordres de grandeur du moment), auxquels peuvent s ajouter des couts d API au token pour les usages intensifs.

Lecture du seuil. Dans cet exemple illustratif, le local (~250 a 400 €/mois, quasi independant du volume apres investissement) devient comparable, puis avantageux, face au cloud des que le nombre de sieges et/ou le volume d appels API croit : au-dela d une dizaine ou d une quinzaine d utilisateurs actifs, ou pour des volumes de tokens eleves, le cout marginal proche de zero du local penche en sa faveur. En dessous, pour un usage leger et peu d utilisateurs, le cloud peut rester moins cher car il evite le CAPEX. Ces bornes sont des hypotheses a recalculer avec les prix reels du materiel, de l electricite locale et du devis cloud.

L argument TCO honnete est donc un calcul de seuil, pas une superiorite absolue : au-dela d un certain volume de requetes et/ou d un certain nombre de sieges, le cout marginal proche de zero du local peut devenir plus avantageux que l OPEX cloud metre au token et par siege, selon l amortissement du CAPEX et le cout local de l electricite et de la maintenance.

## 6. Pieges argumentaires a eviter

Ces quatre arguments sont refutes par la verification adversariale. Ils doivent etre bannis du discours commercial, avec la raison.

### (a) « Eux tous cloud-only, nous seuls en local » — FAUX

Refute. Gemini fonctionne on-premises voire totalement air-gapped chez le client via Google Distributed Cloud, en disponibilite generale depuis le 28 aout 2025 (Google Cloud, 2025). Mistral Le Chat Enterprise est self-hostable (Mistral AI, s. d.). Des capacites Windows on-device (Phi Silica) tournent en local sur NPU (Microsoft, s. d.-a). Il faut donc reconnaitre l existence de ces modes et deplacer l argument vers la simplicite et le caractere structurel de la souverainete JARVIS. Nuances a garder en tete : le mode Gemini air-gapped GA suppose du materiel dedie fourni par Google et vise les clients a tres fortes exigences de souverainete ; le mode GDC connected reste en preview en 2026.

### (b) « Cout zero chez nous vs eux payants » — TROP ABSOLU

A eviter. Cela ignore le TCO local (CAPEX GPU, electricite, maintenance) et le fait que les concurrents proposent aussi de l on-prem a cout fixe. La formulation correcte est celle de la section 5 : cout marginal par requete tres bas apres investissement, a comparer au cout metre du cloud selon le volume et le nombre de sieges.

### (c) « Nous seuls citons nos sources » — FAUX

Refute. Perplexity affiche des citations numerotees inline par defaut ; Gemini via Grounding with Google Search renvoie des annotations de citation (Google, s. d.-b) ; Microsoft Copilot Chat inclut des citations inline avec un panneau Sources. La citation verifiable n est donc pas un differenciateur exclusif. Nuances : chez Gemini et Copilot, ces citations n apparaissent qu en mode grounded/connecte ; et une citation prouve la tracabilite, pas l exactitude. Sur ce dernier point, une etude de la Columbia Journalism Review, non repliquee, suggere que Perplexity peut citer une source qui ne soutient pas l affirmation (de l ordre de 37 % de reponses erronees dans ce test) ; il faut la presenter comme un signal isole, non comme une preuve generale du comportement des moteurs a citations. L angle honnete est la souverainete et le fait que les sources restent locales et privees, pas l existence des citations.

### (d) « Eux inutilisables hors-ligne » — FAUX

Refute. Gemini sur GDC air-gapped fonctionne deconnecte d internet (Google Cloud, 2025) ; Phi Silica fournit des capacites generatives locales sur NPU sans connexion cloud, comme la generation, le resume, la reecriture et le text-to-table (Microsoft, s. d.-a). Nuance importante : ce qui est hors-ligne cote Microsoft, ce sont des fonctions Windows on-device propulsees par Phi Silica, PAS l assistant de marque Microsoft Copilot / Microsoft 365 Copilot, qui reste cloud-first et exige une connexion. De plus, Microsoft fait evoluer ses modeles on-device (un remplacant de Phi Silica est annonce a horizon fin 2026) ; c est donc une cible mouvante a revalider.

## 7. Recommandations concretes pour le pitch commercial de Christophe

1. Tenir l angle souverainete structurelle, pas exclusivite du local. Dire : « chez nous, en configuration locale, la non-exfiltration decoule de l architecture, pas d une clause contractuelle a auditer chez un tiers. » Ne jamais affirmer etre le seul a pouvoir tourner en local.
2. Mettre en avant les deux differenciateurs solides. Non-exfiltration dans la configuration locale (section 4.1) et conformite UE facilitee, journal append-only, pas de franchissement de frontiere, risque CLOUD Act reduit (section 4.2).
3. Assumer les chiffres exacts et distinguer leur niveau de preuve. Auditables sur board.db : 52 experts, 18 domaines, 312 976 documents-sources, 1 078 513 chunks (dire « chunks », pas « documents » ; ne pas dire « plus d un million de documents »), 99,7 % vectorises en 768D. Compteurs internes non audites : 653 outils MCP, 211 270 skills — a presenter comme tels, avec une definition operationnelle de « skill » et « expert ».
4. Cadrer le cout en TCO, pas en « gratuit ». Presenter le seuil de rentabilite illustratif (section 5.1) : cout marginal proche de zero au-dela d un volume et d un nombre de sieges, a opposer au cout metre au token et par siege du cloud, en reconnaissant CAPEX et electricite, et en presentant tout tarif comme un ordre de grandeur a revalider au devis.
5. Bannir les quatre pieges de la section 6. Un prospect averti connait Gemini GDC, Mistral self-hosted, Perplexity et Phi Silica : utiliser un argument refute detruirait la credibilite.
6. Nuancer le 0 token et la localite. Preciser « pour cette configuration, inference et voix en local, noeuds cloud optionnels desactives » et mentionner que ces noeuds existent au niveau systeme, pour rester exact et credible.
7. Cibler les secteurs a forte contrainte reglementaire (sante, defense, secteur public, finance) ou l argument de souverainete et de conformite pese le plus lourd, tout en mentionnant que des offres de cloud souverain UE existent aussi cote concurrents.

## 8. Limites de l etude, tracabilite et terminologie

### 8.1 Limites

- Les metriques auditables JARVIS (section 2a) proviennent d une seule instance a un instant donne (comptes SQL live sur `board.db`, 2026-09-16) ; elles n ont pas ete auditees par un tiers independant et peuvent varier dans le temps.
- Les compteurs internes (section 2b : 653 outils MCP, 211 270 skills, 22 Go VRAM, 0 token) ne sont pas dans `board.db` et ne sont pas audites ; ils dependent de definitions operationnelles a publier.
- Les comparaisons de qualite d inference, de latence et de precision entre JARVIS et les modeles cloud n ont pas ete mesurees ici ; le rapport porte sur la souverainete, la conformite et le cout, pas sur la performance brute des modeles.
- Les tarifs et noms de modeles cloud cites sont des ordres de grandeur indicatifs, datables et partiellement promotionnels ; ils evoluent et certains ne sont pas publies officiellement. Tout chiffre doit etre revalide sur la page tarifaire officielle a la date du devis.
- Les capacites on-premises et hors-ligne des concurrents sont des cibles mouvantes (evolution des modeles on-device Microsoft, GDC connected en preview) ; l etat exact peut changer apres septembre 2026.
- Les affirmations de conformite (RGPD, NIS2, reglement IA, CLOUD Act) sont un cadrage de gouvernance, pas un avis juridique ; une analyse de conformite formelle par un juriste reste necessaire pour tout deploiement.
- Le verdict sur les citations s appuie notamment sur un test de la Columbia Journalism Review, non replique, dont la representativite est limitee.

### 8.2 Tracabilite de la verification

Les verdicts de verification (confirme, partiellement confirme, refute) qui figurent dans ce rapport proviennent d une verification par des agents sur les sources officielles listees en section 9 (dates d acces : septembre 2026). Il ne s agit PAS d un audit realise par un tiers independant : c est une verification documentaire interne au pipeline de deep-research, dont la portee se limite a la confrontation des affirmations aux sources primaires citees. Les valeurs de la section 2a ont ete obtenues par requetes SQL directes en lecture seule.

### 8.3 Uniformisation terminologique

Dans tout ce rapport et toute communication derivee, employer strictement le triptyque « documents-sources / documents / chunks » : environ 313 000 documents-sources, fragmentes en environ 1,08 million (1 078 513) de chunks. Ne jamais employer « documents » comme synonyme de « chunks ».

## 9. References

Chaque fait concurrent est rattache a sa source primaire distincte (style APA simplifie avec URL, acces septembre 2026).

- Anthropic. (2025a). *Updates to our consumer terms*. https://www.anthropic.com/news/updates-to-our-consumer-terms
- Anthropic. (s. d.-b). *Pricing*. https://claude.com/pricing
- Google. (s. d.-a). *Gemini API pricing and models*. https://ai.google.dev/
- Google. (s. d.-b). *Grounding with Google Search — Gemini API documentation*. https://ai.google.dev/gemini-api/docs/google-search
- Google. (s. d.-c). *Apps Gemini : donnees et confidentialite (aide)*. https://support.google.com/gemini/answer/13594961
- Google Cloud. (2025, 28 aout). *Gemini is now available anywhere* (blog Google Cloud). https://cloud.google.com/blog/topics/hybrid-cloud/gemini-is-now-available-anywhere
- Microsoft. (s. d.-a). *Phi Silica transparency note*. https://learn.microsoft.com/en-us/windows/ai/apis/phi-silica-transparency-note
- Microsoft. (s. d.-b). *Microsoft 365 Copilot — Enterprise Data Protection*. https://learn.microsoft.com/en-us/microsoft-365/copilot/enterprise-data-protection
- Mistral AI. (s. d.). *Le Chat Enterprise*. https://mistral.ai/news/le-chat-enterprise/
- OpenAI. (s. d.). *Pricing*. https://openai.com/pricing
- OpenAI. (2025). *Enterprise privacy*. https://openai.com/enterprise-privacy/

Note sur les verdicts : Gemini air-gapped GA + GDC connected en preview (Google Cloud, 2025 — partiellement confirme) ; Mistral self-hosted (Mistral AI, s. d. — confirme) ; Phi Silica hors-ligne on-device mais pas l assistant Copilot complet (Microsoft, s. d.-a — partiellement confirme) ; exclusivite des citations refutee (Google, s. d.-b ; Perplexity ; Microsoft) ; coexistence facturation token + siege (Anthropic, s. d.-b ; Google, s. d.-a ; OpenAI, s. d. — confirme).

## 10. Declaration d usage d outils d IA

Ce rapport a ete redige par un agent d IA (Claude, Anthropic) agissant comme compilateur de rapport au sein d une equipe de deep-research. Les metriques auditables de l instance JARVIS (section 2a) ont ete obtenues par comptes SQL en direct sur `board.db` ; les compteurs internes (section 2b) sont remontes par le systeme et non audites. Les faits relatifs aux concurrents cloud proviennent de sources officielles fournisseurs citees individuellement en section 9, avec des verdicts de verification adversariale (confirme, partiellement confirme, refute) signales dans le texte. Cette verification a ete effectuee par des agents sur ces sources, et ne constitue pas un audit tiers independant. L agent n a pas realise de mesures de performance independantes lors de cette compilation ; il a synthetise, structure et redige a partir du dossier de donnees et de sources transmis. Toute affirmation, et en particulier tout tarif ou nom de modele (donne en ordre de grandeur indicatif), doit etre revue et revalidee par un humain sur les pages officielles avant usage commercial ou juridique.
