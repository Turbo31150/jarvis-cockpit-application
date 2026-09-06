# LM Studio dans le Cockpit JARVIS — usage & doctrine

Inférence **locale, 0 token, illimitée** via LM Studio (API OpenAI-compatible).
LM Studio est le **tier-0 prioritaire** du moteur d'inférence du cockpit ; si
aucun modèle n'est résident, on retombe proprement sur Ollama puis le nœud M6
distant puis le proxy chat.

## Endpoints

LM Studio écoute sur `0.0.0.0:1234` → joignable par **deux adresses équivalentes**
(même process) :

| Adresse | Contexte |
|---|---|
| `http://127.0.0.1:1234` | loopback, depuis la machine |
| `http://192.168.42.241:1234` | IP tether USB du rig (interface `enx*`), depuis le téléphone / app mobile |

Le tier-0 essaie, dans l'ordre : `JARVIS_LMSTUDIO_URL` → `127.0.0.1:1234` →
`192.168.42.241:1234`. Premier port TCP ouvert gagne.

## Doctrine matérielle — rig « mining » (PCIe x1)

> Réf. Notion : ⛏️ « M6 — le rig de minage reconverti » + « Infrastructure backends & board ».

Le rig est un Acer TC-605 (2014, i5-4460, 16 Go DDR3) avec **4 GPU sur risers
PCIe x1** (2× GTX 1660 SUPER, RTX 2060, RTX 3080, ~34 Go VRAM). Le bus x1 = **1/32**
du débit x16.

**Conséquence clé** : charger un modèle ~9 Go prend des **minutes** → l'API renvoie
`HTTP 000` / `Engine protocol startup was aborted` (faux échec), mais le serveur
finit de charger. Une fois en VRAM, l'inférence tourne **sans retoucher le bus : ~2,2 s**.

### Règles appliquées par le code

1. **Jamais de JIT-load en ligne.** La sélection du modèle lit `/api/v0/models`
   (endpoint natif LM Studio, champ `state`) et ne retient qu'un modèle déjà
   `loaded`. Sinon → tier-0 sauté, repli Ollama. On ne demande jamais un modèle
   « présent sur disque mais non chargé » (ce que fait `/v1/models`, qui déclenche
   un JIT-load qui fige l'API sur x1).
2. **Précharger avec TTL infini.** Tout déchargement coûte des minutes de
   rechargement. Charger une fois au démarrage : `lms load <modele> --gpu max -y`.
3. **1 modèle par carte, jamais de split multi-GPU** (chaque découpe multiplie
   les transferts sur le bus x1).
4. **`/nothink`** est préfixé au prompt pour les modèles à raisonnement
   (`qwen3*`, `deepseek-r1*`) afin de couper le bloc `<think>` à la source ; un
   strip `</think>` reste en filet de sécurité.
5. **Garde thermique** (télémétrie) : la GTX 1660 SUPER n'a plus de ventilateur
   (82-91 °C oisive) → exclue du `max()` d'alerte, son détail reste affiché.

## Modèles

Installés (`~/.lmstudio/models/ollama-local/`) :

| Modèle | Rôle |
|---|---|
| `qwen3-8b` | chat principal / analyse (préféré n°1) |
| `gemma3-4b` | modèle léger/rapide (préféré, léger sur VRAM) |
| `qwen2.5-7b` | secondaire / délestage |
| `mistral-7b-instruct` | alternatif |
| `deepseek-r1-7b` | raisonnement (`/nothink`) |
| `qwen3-1.7b` / `qwen2.5-1.5b` | petits / rapides |
| `nomic-embed-text-latest` | embeddings |

> `gemma3.5` figure dans la liste de préférence mais **n'est pas encore installé** ;
> il sera automatiquement utilisé s'il est chargé un jour (sélection résident-only).

## Configuration (variables d'environnement)

| Variable | Défaut | Effet |
|---|---|---|
| `JARVIS_LMSTUDIO_URL` | *(vide)* | force une base LM Studio en tête de liste |
| `JARVIS_LMSTUDIO_MODELS` | `qwen3-8b, gemma3.5, gemma3-4b, qwen2.5-7b, mistral-7b-instruct, deepseek-r1-7b, qwen3-1.7b` | ordre de préférence (CSV) |
| `JARVIS_M1_HOST` | `127.0.0.1` | hôte LM Studio de la table ronde |

## Vérifier / piloter

```bash
# Modèles chargés (résidents) et leur état :
curl -s http://127.0.0.1:1234/api/v0/models | jq '.data[] | {id, state, type}'

# Charger un modèle en VRAM (une fois, TTL long) :
lms load qwen3-8b --gpu max -y     # ou gemma3-4b

# Tester l'inférence 0-token du cockpit :
python3 -c "import sys;sys.path.insert(0,'cockpit');from core.inference import generate_completion as g;print(g('Bonjour')['source'])"
```

Une réponse `source = "LM Studio LOCAL (<modele>, 0 token)"` confirme le tier-0.
Pendant qu'un modèle charge (HTTP 000), c'est normal : le cockpit sert via Ollama
en attendant, sans blocage.
