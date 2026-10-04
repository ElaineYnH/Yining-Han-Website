# Yining Han's website

Personal website and AEDS 6400 blog posts, built with Quarto and published using GitHub Pages.

Website: https://elaineynh.github.io/Yining-Han-Website/

## Find each post's article and code

| Post | Article source | Code and replication |
|---|---|---|
| 1: Mathematical/statistical concept | `blog/posts/post1/blog1-260906.qmd` | Explanation and any embedded code are in the article source |
| 2: SEPTA web scraping | `blog/posts/post2/blog2.qmd` | R scraping and analysis are embedded in the article source; saved data are in `blog/posts/post2/data/` |
| 3: Education and the labor market | `blog/posts/post3/blog3.qmd` | Start with [`post3/README.md`](blog/posts/post3/README.md); the IPUMS preparation script is `blog/posts/post3/prepare_cps.R` |
| 4: New-home prices and mortgage payments | `blog/posts/post4/blog4.qmd` | Start with [`post4/README.md`](blog/posts/post4/README.md); the complete Python analysis is `blog/posts/post4/code/analyze.py` |

Blog 4 has separate `code/`, `data/`, and `results/` folders. It includes its original downloaded data snapshots, source metadata, package versions, generated figures and tables, and one-command replication instructions. Its supplied article and figures are ready to publish; publishing does not require running Python.

## Website layout

- `_quarto.yml`: site configuration and output directory.
- `index.qmd`, `bio.qmd`, `resume.qmd`: main pages.
- `blog/index.qmd`: blog listing, which discovers posts under `blog/posts/`.
- `blog/posts/postN/`: each post's article and supporting files.
- `images/` and `files/`: profile images and downloadable files.
- `styles.css`: site styling.
- `.github/workflows/deploy.yml`: automatic render and deployment.
- `docs/`: rendered output used by the deployment workflow.

## Publish

Edit the source files in VS Code, save, commit, and push to `main`. The existing **Build and Deploy Quarto Website** GitHub Actions workflow installs its R and Quarto dependencies, runs `quarto render`, and publishes the resulting `docs` directory. New articles under `blog/posts/` are added to the blog listing automatically.

No manual edits to rendered HTML or the `docs` directory are needed. Local rendering is optional; the automated workflow handles it. To preview locally when Quarto and the required R packages are installed:

```bash
quarto preview
```

See each post's README or source file for its own data requirements and analysis instructions.
