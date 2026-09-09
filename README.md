# Wiki Makera en français

Bibliothèque personnelle issue de l’export du wiki Makera : 91 pages accessibles,
leurs versions anglaises et 548 illustrations locales. Les sept liens renvoyant
une erreur 404 sont répertoriés sur la page « État de la copie & sources ».

## Consulter

Ouvrir `site/index.html` directement dans un navigateur fonctionne sans serveur,
y compris la recherche. Lorsque le serveur local tourne, ouvrir
<http://127.0.0.1:8768/>.

Pour relancer ce serveur sur le Mac :

```bash
task --dir ~/Documents/GitHub/my-apps/makera serve
```

Il écoute seulement sur `127.0.0.1`. `Ctrl+C` arrête le serveur ; les fichiers du
site restent consultables directement. Le dossier `site/` contient la totalité
de la bibliothèque navigable et peut être déplacé ou sauvegardé.

## Contenu et limites

Les textes ont été traduits par Luna, avec des corrections ciblées lors de la
relecture. Ce n’est pas une traduction officielle de Makera. Chaque article
permet de consulter sa version anglaise et la page source du wiki.

Les textes intégrés aux images et captures d’écran restent dans leur langue
d’origine. Les vidéos, fichiers à télécharger et autres ressources externes
s’ouvrent en ligne. Les illustrations intégrées aux articles sont sauvegardées
dans `site/assets/media/`.

## Fichiers et reconstruction

- `sources/` et `source-cache/` : HTML fournis par l’export utilisateur.
- `originals/` : contenu anglais complet extrait des pages Wiki.js.
- `translation/input/` : textes sources dédupliqués, identifiés par leur empreinte.
- `translation/output/` : traductions Luna assemblées.
- `translation/work/` : petits lots de traduction et sorties correspondantes.
- `translation/corrections.json` : corrections de relecture appliquées au rendu.
- `translation/audit.json` : couverture et contrôles numériques.
- `translation/numeric-reviewed.json` : écarts de notation relus, liés aux textes exacts.
- `site-check.json` : contrôle des liens, images, tableaux et blocs de code.
- `report.json` : inventaire de l’export et liens introuvables.

Reconstruire le site après des corrections de traduction :

```bash
task --dir ~/Documents/GitHub/my-apps/makera build
```

Le build final refuse les traductions manquantes, les valeurs invalides et les
écarts numériques non relus. Le mode d’aperçu interne est explicitement marqué
comme incomplet. Les scripts ne modifient pas les sauvegardes HTML originales.

Source : <https://wiki.makera.com/en/GettingStarted>. Aucun déploiement sur le
homelab ni modification de service de production n’est nécessaire pour consulter
cette copie sur le Mac.

## Publication Netlify

Le dépôt contient déjà le site statique généré dans `site/`. Les paramètres
Netlify sont décrits dans `netlify.toml` :

- **Build command** : `test -f site/index.html && test -f site/assets/style.css && test -f site/assets/app.js && test -f site/assets/search-data.js && test -f site/fr/58aad18200dc6379fe3c.html`
- **Publish directory** : `site`
- **Base directory** : laisser vide
- **Functions directory** : laisser vide
- **Branch** : la branche publiée de ton choix, généralement `main`

Le build Netlify utilise uniquement `test`, disponible dans l’environnement Linux,
vérifie les fichiers statiques déjà générés puis publie `site/`. Il ne
retélécharge pas le wiki et ne dépend donc pas de Trafilatura ou de l’accès au
site Makera. Les archives brutes `.gz` restent locales et sont exclues par
`.gitignore`. Après une modification locale, lancer `task netlify:check`, puis
committer `site/` et les traductions concernées avant de pousser.
