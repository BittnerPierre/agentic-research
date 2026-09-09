# Main courante et retex

## `journal.md` — la main courante

Une note qui se transmet d'étape en étape et se lit après coup. Une entrée par
événement, horodatée si possible, courte :

```markdown
# Journal
- [étape 1] Cadrage écrit. Brief muet sur la langue → défaut : langue du brief (anglais).
- [étape 2] D3 (guidance) ne couvre que trois sociétés ; les trois autres seront déclarées « non disponible ».
- [étape 3] 34 extraits, sous-agents : 1 par document. Doublon E11/E19 fusionné → E19 retiré (retenu:false).
- [étape 4] Contradiction D2/D4 sur le capex Apple : les deux valeurs conservées, à rapporter telles quelles.
- [étape 7] Relecteur : 2 citations ne soutenaient pas la phrase → reformulé ; 1 chiffre arrondi différemment → recopié.
- [étape 7] Manque : aucun extrait sur Q5 → aller-retour 1/1 vers l'étape 3 → 2 extraits ajoutés.
- [étape 8] Livré. 1 640 mots hors Sources.
```

Ce qu'on y note : décisions par défaut, documents absents ou inaccessibles,
renvois (« voir l'info dans D2 et non D1 »), numéro de révision, allers-retours
consommés, tours/temps estimés par étape.

## `retex.md` — relecture de processus (fin de run)

Sert à améliorer le **processus** au run suivant, pas la recherche sur ce
thème. Il est relu par l'humain puis éventuellement donné en entrée
(`process-notes.md`) d'un run ultérieur. Il ne contient donc **aucun contenu
sur les sources** (pas de fait, pas de chiffre, pas de nom de document) —
uniquement méthode, outils, formats, pièges :

```markdown
# Retex processus
## Ce qui a bien marché
- Un sous-agent par document avec le contrat d'extrait : extraits propres, aucun doublon inter-documents.
## Ce qui a mal marché
- La recherche sémantique renvoyait des extraits trop courts pour les tableaux : ajouter une passe de lecture intégrale des fichiers tabulaires.
## À changer la prochaine fois
- Remplir la grille de vérification pendant la rédaction plutôt qu'après.
## Budget consommé (estimation)
- Étape 3 : ~40 % des tours. Étape 7 : ~20 %.
```
