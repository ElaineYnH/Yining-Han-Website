# Refresh the public Python.org snapshot explicitly:
# Rscript blog/posts/post2/code/scrape.R --refresh
# Default analysis/rendering uses saved files and makes no requests.
suppressPackageStartupMessages(library(httr2))
suppressPackageStartupMessages(library(rvest))
suppressPackageStartupMessages(library(jsonlite))

file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
if (length(file_arg) != 1L) stop("Run this file with Rscript.")
root <- dirname(dirname(normalizePath(sub("^--file=", "", file_arg))))
source(file.path(root, "code", "parse.R"))
if (!("--refresh" %in% commandArgs(TRUE))) {
  stop("A network refresh requires --refresh. Use analyze.R for offline reproduction.")
}

base <- "https://www.python.org"
user_agent <- "YiningHan-AEDS6400-Blog2/1.0 (educational; low-frequency)"
raw_dir <- file.path(root, "data", "raw")
dir.create(file.path(raw_dir, "details"), recursive = TRUE, showWarnings = FALSE)
request_log <- list()

fetch <- function(url) {
  if (!startsWith(url, paste0(base, "/"))) stop("Only public Python.org URLs are allowed.")
  Sys.sleep(1.5)
  response <- request(url) |>
    req_user_agent(user_agent) |>
    req_timeout(30) |>
    req_perform()
  # httr2 stops on access errors. No login, alternate host, CAPTCHA workaround,
  # employer application page, or automatic retry is used.
  body <- resp_body_string(response)
  request_log[[length(request_log) + 1L]] <<- list(
    url = url, status = resp_status(response),
    fetched_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE)
  )
  body
}

robots <- fetch(paste0(base, "/robots.txt"))
writeLines(robots, file.path(raw_dir, "robots.txt"), useBytes = TRUE)
lines <- trimws(sub("#.*$", "", strsplit(robots, "\n", fixed = TRUE)[[1L]]))
general <- which(grepl("^User-agent:[[:space:]]*\\*$", lines, ignore.case = TRUE))
disallowed <- character()
for (start in general) {
  remaining <- seq.int(start + 1L, length(lines))
  following_agent <- remaining[grepl("^User-agent:", lines[remaining], ignore.case = TRUE)]
  finish <- if (length(following_agent)) following_agent[1L] - 1L else length(lines)
  if (finish > start) {
    block <- lines[seq.int(start + 1L, finish)]
    disallowed <- c(disallowed, trimws(sub("^[^:]+:", "",
      block[grepl("^Disallow:", block, ignore.case = TRUE)])))
  }
}
check_allowed <- function(url) {
  path <- sub("\\?.*$", "", sub(base, "", url, fixed = TRUE))
  for (rule in disallowed[nzchar(disallowed)]) {
    # The current file has literal prefixes. Stop for unfamiliar wildcard rules
    # so a future policy change requires review instead of being ignored.
    if (grepl("[*$]", rule)) stop("Review changed robots wildcard rules before refreshing.")
    if (startsWith(path, rule)) stop(paste("robots.txt disallows", path))
  }
  if (!startsWith(path, "/jobs/")) stop("Unexpected crawl path.")
}

index_urls <- character()
index_files <- character()
url <- paste0(base, "/jobs/")
repeat {
  if (url %in% index_urls || length(index_urls) >= 5L) stop("Unexpected pagination loop/size.")
  check_allowed(url)
  html <- fetch(url)
  page <- read_html(html)
  container <- html_element(page, "ol.list-recent-jobs")
  if (inherits(container, "xml_missing")) stop("No listing found.")
  filename <- sprintf("index_%02d.html", length(index_urls) + 1L)
  # Retain only the factual listing cards, not site navigation or full prose.
  writeLines(as.character(container), file.path(raw_dir, filename), useBytes = TRUE)
  index_urls <- c(index_urls, url)
  index_files <- c(index_files, filename)
  next_href <- html_attr(html_elements(page,
    ".pagination a[rel='next'], .pagination .next a, a.next"), "href")
  next_href <- unique(next_href[!is.na(next_href)])
  if (length(next_href) == 0L) break
  if (length(next_href) != 1L) stop("Ambiguous next page link.")
  url <- xml2::url_absolute(next_href, url)
}

postings <- do.call(rbind, lapply(file.path(raw_dir, index_files), parse_listing))
if (anyDuplicated(postings$job_id)) postings <- postings[!duplicated(postings$job_id), ]
postings <- deduplicate_roles(postings)
roles <- postings[postings$keep_for_analysis, ]
for (i in seq_len(nrow(roles))) {
  check_allowed(roles$source_url[i])
  page <- read_html(fetch(roles$source_url[i]))
  heading <- html_element(page, xpath = "//h2[normalize-space(.)='Restrictions']")
  restrictions <- html_element(page,
    xpath = "//h2[normalize-space(.)='Restrictions']/following-sibling::ul[1]")
  if (inherits(heading, "xml_missing") || inherits(restrictions, "xml_missing")) {
    stop(paste("Restrictions not found for", roles$job_id[i]))
  }
  # Preserve original field HTML unchanged; exclude full job descriptions,
  # contact emails, application forms, and personal contact names.
  fragment <- paste(as.character(heading), as.character(restrictions), sep = "\n")
  filename <- file.path(raw_dir, "details", paste0(roles$job_id[i], ".html"))
  writeLines(fragment, filename, useBytes = TRUE)
  parse_detail(filename) # Fail immediately if a selector or field changed.
  message(sprintf("Collected %d/%d: %s", i, nrow(roles), roles$job_id[i]))
}

manifest <- list(
  source = "Python.org public Job Board",
  scope = "All posting cards visible on the board; newest posting per employer-title pair retained.",
  index_urls = index_urls, index_files = index_files,
  raw_postings = nrow(postings), retained_roles = nrow(roles),
  detail_ids = roles$job_id,
  user_agent = user_agent, pause_seconds = 1.5,
  requests = request_log,
  capture_date_utc = format(Sys.time(), tz = "UTC", format = "%Y-%m-%d"),
  storage_note = "Original factual HTML fragments only; full pages and descriptions are not redistributed."
)
write_json(manifest, file.path(root, "data", "manifest.json"), pretty = TRUE, auto_unbox = TRUE)
message(sprintf("Saved %d postings / %d employer-title entries; %d requests in this refresh.",
                nrow(postings), nrow(roles), length(request_log)))
