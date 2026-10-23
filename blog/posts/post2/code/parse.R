# Shared extraction and cleaning. No network requests are made in this file.
suppressPackageStartupMessages(library(rvest))

squish <- function(x) trimws(gsub("[[:space:]]+", " ", x))

parse_listing <- function(path) {
  page <- read_html(path, encoding = "UTF-8")
  nodes <- html_elements(page, "ol.list-recent-jobs > li")
  if (length(nodes) == 0L) stop("No job cards found: inspect the page selectors.")
  rows <- lapply(nodes, function(node) {
    title_node <- html_element(node, ".listing-company-name > a")
    href <- html_attr(title_node, "href")
    if (is.na(href) || !grepl("^/jobs/[0-9]+/$", href)) {
      stop("Unexpected job link in the listing.")
    }
    company_node <- read_html(as.character(html_element(node, ".listing-company-name")), encoding = "UTF-8")
    xml2::xml_remove(html_elements(company_node, "a, .listing-new, br"))
    posted <- html_attr(html_element(node, "time"), "datetime")
    data.frame(
      job_id = as.integer(sub("^/jobs/([0-9]+)/$", "\\1", href)),
      title = squish(html_text2(title_node)),
      company = squish(html_text2(html_element(company_node, ".listing-company-name"))),
      location = squish(html_text2(html_element(node, ".listing-location"))),
      posted_at = posted,
      posted_date = substr(posted, 1L, 10L),
      job_types = squish(html_text2(html_element(node, ".listing-job-type"))),
      source_url = paste0("https://www.python.org", href),
      stringsAsFactors = FALSE
    )
  })
  result <- do.call(rbind, rows)
  if (anyNA(result[c("job_id", "title", "company", "location", "posted_date")]) ||
      any(result$title == "" | result$company == "")) {
    stop("Missing required listing fields; do not silently count them.")
  }
  result
}

deduplicate_roles <- function(postings) {
  # The unit is an advertised employer-title combination, not a verified vacancy.
  # Keep the newest visible posting; job_id resolves any date tie.
  postings$role_key <- paste(tolower(squish(postings$company)),
                            tolower(squish(postings$title)), sep = " | ")
  postings <- postings[order(postings$posted_at, postings$job_id, decreasing = TRUE), ]
  postings$keep_for_analysis <- !duplicated(postings$role_key)
  rownames(postings) <- NULL
  postings
}

parse_detail <- function(path) {
  page <- read_html(path, encoding = "UTF-8")
  items <- html_elements(page,
    xpath = "//h2[normalize-space(.)='Restrictions']/following-sibling::ul[1]/li")
  texts <- squish(html_text2(items))
  remote_items <- texts[texts %in% c("Telecommuting is OK", "No telecommuting")]
  if (length(remote_items) != 1L) {
    stop(paste("Expected one unambiguous telecommuting field in", basename(path)))
  }
  data.frame(
    telecommuting_field = remote_items,
    telecommuting_ok = remote_items == "Telecommuting is OK",
    stringsAsFactors = FALSE
  )
}
