# CAHIER DES CHARGES FONCTIONNEL & TECHNIQUE (CDCF)
## Produit : JARVIS Box — Appliance RAG Souveraine 0-Token
### Version : 1.0.0-PROD | Date : 15 Septembre 2026 | Statut : Officiel & Validé

---

## 1. VISION & CADRAGE STRATÉGIQUE

### 1.1 Objet du Document
Le présent document formalise le cahier des charges pour l'industrialisation, la sécurisation et la commercialisation de la **« JARVIS Box »**, une appliance matérielle et logicielle d'intelligence artificielle locale, souveraine, à coût-token nul, destinée aux organisations régulées à strictes contraintes de confidentialité.

### 1.2 Pivot & Rupture Doctrinale
- **Abandon du récit antérieur** : Cessation définitive de la communication sur un « OS IA universel à 10 521 skills et 700 outils MCP ». Ce positionnement est non qualifié pour l'entreprise, survendu et non défendable.
- **Adoption du positionnement cible** : **« L'Appliance RAG Souveraine 0-Token à Réponses Citées et Auditables »**.
- **Devise produit** : *« Chaque réponse cite formellement sa source ou est rejetée — vérifiable en direct par votre DPO en SQL. Zéro donnée ne franchit vos murs. »*

---

## 2. SEGMENTATION & CIBLES COMMERCIALES

### 2.1 Cible Prioritaire (P0) : Cabinets Régulés Mono-Site
Organisation de 1 à 15 collaborateurs opérant dans un environnement légalement contraint :
1. **Cabinets d'Avocats** (Secret professionnel strict, Art. 66-5 loi du 31 décembre 1971).
2. **Cabinets d'Expertise Comptable & Commissariat aux Comptes** (Secret professionnel, conformité déontologique).
3. **Offices Notariaux** (Conservation des actes, authenticité et intégrité absolue).
4. **Cabinets Médicaux Spécialisés & Cliniques** (Hébergement de Données de Santé - HDS, RGPD strict).

### 2.2 Proposition de Valeur Client
- **Zéro fuite réseau** : Inférence 100 % on-premise, déconnectable d'Internet sans altération fonctionnelle.
- **Zéro abonnement variable au token** : Coût d'exploitation prévisible, amortissement matériel sur 3 ans.
- **Zéro hallucination non tracée** : Obligation contractuelle de citation. L'utilisateur peut auditer la provenance de chaque mot en 1 clic.

---

## 3. SPÉCIFICATIONS TECHNIQUES DE L'APPLIANCE MATÉRIELLE (« JARVIS BOX »)

### 3.1 Découplage du Banc de R&D
Le rig actuel (`mining`, i5-3450 sans AVX2, DDR3) reste cantonné au statut de **banc de test de laboratoire**. Les unités commercialisées reposent sur une configuration standardisée et éprouvée.

### 3.2 Spécifications Cibles de la JARVIS Box (Unité Client)

| Composant | Spécification Minimale Requise | Rôle & Justification |
| :--- | :--- | :--- |
| **Châssis** | Boîtier Mini-Tour compact insonorisé (Micro-ATX ou Mini-ITX) | Intégration discrète sous un bureau de direction ou baie technique. |
| **Processeur** | AMD Ryzen 5 7600X ou Intel Core i5-14400 (support complet AVX2 / AVX-512) | Prétraitement vectoriel, extraction de documents et tokenisation rapide. |
| **Mémoire Vive** | 64 Go DDR5 (2 x 32 Go) 5600 MHz ECC ou non-ECC | Hébergement du moteur FTS5, cache SQLite WAL et mémoire vive de travail. |
| **Accélérateur IA** | NVIDIA GeForce RTX 4070 Ti Super 16 Go VRAM (ou RTX 4080 16 Go) | Modèles locaux 8B à 14B quantifiés (Qwen, Mistral) entièrement en VRAM. |
| **Stockage NVMe** | 2 x 2 To NVMe PCIe Gen4 en miroir RAID-1 | RAID-1 matériel/ZFS : OS, corpus `board.db` (7,5 Go) et sauvegardes chiffrées. |
| **Réseau** | Double port Ethernet 2.5 GbE + Switch matériel coupe-circuit physique | Connexion au LAN interne sécurisé sans aucune passerelle externe obligatoire. |

### 3.3 Traitement du SPOF Matériel (Obligation Régulée)
Tout contrat régulé inclut une **Appliance Miroir de Secours passive (Option Haute Disponibilité)** synchronisée quotidiennement, ou un disque extractible chiffré permettant un rétablissement complet en moins de 2 heures en cas de sinistre physique.

---

## 4. ARCHITECTURE LOGICIELLE & MOAT DE DONNÉES

### 4.1 Le Cœur du Moat : Corpus Curé `board.db`
- **Volume vérifié** : 7,4 Go, 1 075 625 fragments curés (chunks), 312 396 sources répertoriées, 48 experts sur 14 domaines d'autorité.
- **Indexation hybride** :
  - *Recherche Lexicale* : SQLite FTS5 plein texte avec BM25 adapté à la langue française.
  - *Recherche Sémantique* : Embeddings 768D (Nomic Embed v1.5) calculés localement sur GPU.
- **Règle de Délibération des 48 Experts** : Consensus pondéré, élimination automatique des biais mono-sources.

### 4.2 La Règle Inviolable Anti-Hallucination
1. **Contrôle en Base de Données** :
   Chaque enregistrement dans la table `answers` doit comporter au moins une liaison vérifiée dans la table `citations` pointant vers un `chunk_id` et une `source` réels.
2. **Vue SQL Réfutable** :
   ```sql
   CREATE VIEW answers_sans_citation AS
   SELECT a.id, a.query_id, a.expert_id, substr(a.text, 1, 80) AS extrait
   FROM answers a
   LEFT JOIN citations c ON c.answer_id = a.id
   WHERE c.id IS NULL;
   ```
3. **Rejet Automatique** : Toute réponse renvoyant une ligne dans `answers_sans_citation` est bloquée avant restitution à l'utilisateur.

### 4.3 Exclusion Stricte du Périmètre Commercial (Table Ronde CDP)
- Le pilotage automatisé des interfaces web propriétaires (ChatGPT, Gemini, Perplexity) via CDP est **formellement exclu de l'offre commerciale**.
- Il ne fait l'objet d'aucun engagement de service (SLA) et reste confiné à un usage de recherche interne non contractuel.

---

## 5. SÉCURITÉ, AUTHENTIFICATION & CONFORMITÉ (P0)

### 5.1 Sécurisation du Cockpit Web (:8600)
- **Authentification forte** : Jeton Bearer chiffré (HMAC-SHA256) ou mot de passe local hashé (Argon2id) obligatoire pour toute requête non-locale (`127.0.0.1`).
- **Cloisonnement réseau** : Écoute par défaut restreinte à `127.0.0.1` ou à l'IP d'administration dédiée sur le sous-réseau du cabinet.

### 5.2 Gestion des Secrets & Credentials
- Remplacement immédiat des fichiers `.env` non chiffrés par un coffre-fort local chiffré (`age` / `sops` ou table SQLite chiffrée avec clé déverrouillée au démarrage de la box par l'administrateur).

### 5.3 Audit de Provenance des Sources
- Campagne d'audit systématique des 312 396 sources de `board.db` pour catégoriser :
  - Domaine public / Législation / Jurisprudence ouverte (100 % pérenne).
  - Documentation technique libre de droit (MIT / CC-BY).
  - Sources à licence réservée (à purger ou remplacer par des équivalents ouverts).

---

## 6. MODÈLE ÉCONOMIQUE, PACKAGING & GRILLE TARIFAIRE

### 6.1 Grille Tarifaire Officielle

| Réf. Offre | Intitulé & Périmètre | Tarif HT | Récurrence |
| :--- | :--- | :--- | :--- |
| **JB-BASE** | **Appliance JARVIS Box Standard**<br>Mini-tour certifiée (Ryzen 5, RTX 4070 Ti Super 16 Go, 64 Go RAM, 2 To RAID-1), Cockpit OS, Corpus 1,07M chunks, déploiement sur site (1/2 journée) et formation cabinet. | **5 900 €** | One-shot |
| **JB-MAINT** | **Contrat Maintien en Condition Opérationnelle (MCO)**<br>Mises à jour de sécurité de l'OS, actualisation trimestrielle des index légaux/fiscaux, télémaintenance chiffrée P2P (Tailscale privé), support J+1 ouvré. | **2 400 € / an**<br>*(200 € / mois)* | Annuel récurrent |
| **JB-CORPUS** | **Ingestion & Vectorisation Métier Sur-Mesure**<br>Numérisation, extraction OCR et vectorisation étanche de la base de précédents et modèles internes du cabinet (jusqu'à 100 000 pages). | **2 500 € à 4 500 €** | Par corpus |
| **JB-REDUND** | **Option Appliance Miroir de Continuité (Anti-SPOF)**<br>Seconde box identique synchronisée en secours immédiat (failover passif). | **2 900 €** | One-shot |

### 6.2 Trajectoire Financière Année 1 (Objectif Réaliste Solo/Duo)
- **Hypothèse conservatrice** : 10 appliances déployées sur les 12 premiers mois.
- **Chiffre d'Affaires Initial (One-shot)** : 10 x 5 900 € = **59 000 € HT**.
- **Revenus Récurrents Annuels (ARR)** : 10 x 2 400 € = **24 000 € HT / an**.
- **Prestations sur-mesure (Corpus client)** : 4 x 3 000 € = **12 000 € HT**.
- **Total Année 1** : **95 000 € HT** (Point mort largement atteint avec 1 à 2 intervenants).

---

## 7. PLAN D'EXÉCUTION TECHNIQUE IMMÉDIAT (P0 EN COURS)

```
[ÉTAPE 1 : IMMÉDIATE] ────────► [ÉTAPE 2 : 30 JOURS] ────────► [ÉTAPE 3 : 90 JOURS]
• Découplage config/paths       • Nettoyage des 204 handlers    • Installeur autonome
• Token auth sur :8600          • Tests d'intégration CI        • Métriques faithfulness
• Vue Cockpit Audit SQL         • Audit provenance board.db     • Prototype boîte client
```

1. **Jalon 1 (Immédiat)** :
   - Mise en place du module de configuration dynamique [`jarvis_config.py`](file:///home/turbo/jarvis/config/jarvis_config.py).
   - Intégration de l'audit SQL des citations en direct dans Cockpit OS (`/api/rag/audit-citations`).
   - Publication du Cahier des Charges dans la visionneuse de documents Cockpit.
2. **Jalon 2 (30 Jours)** :
   - Assainissement des 204 handlers MCP pour éliminer toute dérive d'erreur interne.
   - Durcissement de l'accès Cockpit par mot de passe local ou clé d'administration.
3. **Jalon 3 (90 Jours)** :
   - Assemblage et benchmark de la première « JARVIS Box » matérielle cible.
   - Signature du premier client pilote régulé à 5 900 €.
