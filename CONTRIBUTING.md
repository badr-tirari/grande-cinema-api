# Contribuer — conventions Git

## Branches

| Branche | Rôle | Règles |
|---|---|---|
| `main` | Code en production (déployé automatiquement sur Render) | Protégée : aucun commit direct, merge uniquement depuis `develop` ou `hotfix/*` via merge request |
| `develop` | Intégration de la prochaine version | Merge uniquement via merge request, CI verte obligatoire |
| `feature/<CLE-JIRA>-<description>` | Développement d'une user story | Créée depuis `develop`, fusionnée dans `develop` |
| `fix/<CLE-JIRA>-<description>` | Correction d'un bug trouvé sur `develop` | Créée depuis `develop` |
| `hotfix/<description>` | Correction urgente en production | Créée depuis `main`, fusionnée dans `main` **et** `develop` |
| `release/<x.y.z>` | Préparation d'une version | Créée depuis `develop`, fusionnée dans `main` (tag `vx.y.z`) |

### Règles de nommage

- minuscules, mots séparés par des tirets (`kebab-case`), sans accent ni espace ;
- la clé Jira de la user story (`CINE-7`) fait le lien entre ticket, branche et merge request ;
- description courte orientée fonctionnalité (3 à 5 mots).

Exemples : `feature/CINE-4-register-login`, `feature/CINE-7-book-seats`, `fix/CINE-13-double-booking`, `hotfix/cors-origin`.

## Commits — Conventional Commits

```
<type>(<portée>): <résumé à l'impératif>

[corps facultatif]

Refs: CINE-7
```

Types : `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`.
Exemple : `feat(bookings): réserver plusieurs places pour une séance`.

## Merge request

1. La CI (lint `ruff`, tests `pytest`, couverture ≥ 80 %, analyse SonarCloud) doit être verte.
2. La description reprend la user story, les critères d'acceptation et la façon de tester.
3. Fusion en `--no-ff` pour garder la trace de la fonctionnalité dans l'historique.
4. La branche est supprimée après fusion.
