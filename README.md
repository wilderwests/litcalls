# The Open Call Bulletin

Agregador masivo y **gratuito** de convocatorias de publicación en estudios literarios de todo el mundo.

- **Artículos de revista** (special issues, números monográficos)
- **Capítulos de libro** (volúmenes editados)
- **Monografías** (propuestas de libro)

Clasificado por factor de impacto (Q1–Q4 / Unranked) y filtrable por área temática (12 categorías).

Incluye fuentes internacionales **y españolas** (Dialnet, Brumal, Tropelías, Ecozona, Tonos Digital, etc.).

## Cómo funciona

1. Un script de Python rastrea cada día fuentes públicas de CFPs (WikiCFP, H-Net, Penn CFP, cfplist, Dialnet, portales OJS, editoriales)
2. Filtra solo convocatorias de **publicación** (excluye conferencias)
3. Clasifica por área temática y factor de impacto
4. Genera un JSON estático que alimenta la web
5. GitHub Actions despliega automáticamente en GitHub Pages

**Coste: cero.** GitHub Pages y GitHub Actions son gratuitos.

## Despliegue

### 1. Crea repositorio
[github.com/new](https://github.com/new) → nombre `cfp-tracker` → **no marques** ninguna casilla → Create

### 2. Sube los archivos
En la página del repo → **uploading an existing file** → arrastra todo el contenido:

```
📁 .github/workflows/deploy.yml  ← ¡CARPETA OCULTA! (Mac: Cmd+Shift+. / Windows: mostrar archivos ocultos)
📁 public/
   ├── index.html
   └── data/cfps.json
📁 scripts/
   └── scrape_cfps.py
📄 README.md
```

### 3. Activa Pages
Settings → Pages → Source: **GitHub Actions**

### 4. Primer scrape
Actions → **Scrape CFPs & Deploy** → **Run workflow**

Tu web: `https://TU-USUARIO.github.io/cfp-tracker/`
