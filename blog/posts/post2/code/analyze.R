# Offline reproduction:
# Rscript blog/posts/post2/code/analyze.R
suppressPackageStartupMessages(library(jsonlite))

file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
if (length(file_arg) != 1L) stop("Run this file with Rscript.")
root <- dirname(dirname(normalizePath(sub("^--file=", "", file_arg))))
source(file.path(root, "code", "parse.R"))
manifest <- read_json(file.path(root, "data", "manifest.json"), simplifyVector = TRUE)
raw_dir <- file.path(root, "data", "raw")
results_dir <- file.path(root, "results")
dir.create(file.path(results_dir, "figures"), recursive = TRUE, showWarnings = FALSE)

postings <- do.call(rbind, lapply(file.path(raw_dir, manifest$index_files), parse_listing))
postings <- postings[!duplicated(postings$job_id), ]
postings <- deduplicate_roles(postings)
roles <- postings[postings$keep_for_analysis, ]
details <- do.call(rbind, lapply(roles$job_id, function(id) {
  parse_detail(file.path(raw_dir, "details", paste0(id, ".html")))
}))
rownames(details) <- NULL
rownames(roles) <- NULL
roles <- cbind(roles, details)
roles$remote_text <- grepl("\\bremote\\b|\\btelecommut[a-z]*\\b|work[ -]from[ -]home",
                          paste(roles$title, roles$location), ignore.case = TRUE, perl = TRUE)
roles$worldwide_text <- grepl("\\bworldwide\\b", paste(roles$title, roles$location),
                             ignore.case = TRUE, perl = TRUE)
roles$signal_group <- ifelse(roles$remote_text,
  ifelse(roles$telecommuting_ok, "both_yes", "text_yes_flag_no"),
  ifelse(roles$telecommuting_ok, "flag_yes_no_text", "neither_positive"))
roles$discovery_candidate <- roles$remote_text | roles$telecommuting_ok
roles$one_signal_only <- xor(roles$remote_text, roles$telecommuting_ok)
roles$explicit_remote_conflict <- roles$remote_text & !roles$telecommuting_ok

# Check record coverage and the accounting identities that matter to the claim.
stopifnot(nrow(postings) == manifest$raw_postings,
          nrow(roles) == manifest$retained_roles,
          !anyDuplicated(roles$role_key), !anyNA(roles$telecommuting_ok),
          setequal(roles$job_id, manifest$detail_ids))
groups <- c("both_yes", "text_yes_flag_no", "flag_yes_no_text", "neither_positive")
counts <- as.integer(table(factor(roles$signal_group, levels = groups)))
stopifnot(sum(counts) == nrow(roles),
          sum(roles$discovery_candidate) == sum(counts[1:3]))
signal_counts <- data.frame(signal_group = groups, roles = counts,
                           share_percent = 100 * counts / nrow(roles))

write.csv(postings, file.path(root, "data", "listing_snapshot.csv"), row.names = FALSE, na = "")
write.csv(roles, file.path(results_dir, "roles_classified.csv"), row.names = FALSE, na = "")
write.csv(signal_counts, file.path(results_dir, "signal_counts.csv"), row.names = FALSE)
queue <- roles[roles$discovery_candidate,
  c("company", "title", "location", "telecommuting_field", "explicit_remote_conflict", "source_url")]
queue$next_step <- ifelse(queue$explicit_remote_conflict,
  "Clarify the conflicting remote statements before tailoring an application",
  "Read the current employer ad for country, working hours, and engagement eligibility")
write.csv(queue, file.path(results_dir, "review_queue.csv"), row.names = FALSE)

summary <- list(
  capture_date_utc = manifest$capture_date_utc,
  raw_postings = nrow(postings), employer_title_entries = nrow(roles),
  distinct_employers = length(unique(tolower(roles$company))),
  repeated_employer_title_postings_removed = sum(!postings$keep_for_analysis),
  remote_title_or_location = sum(roles$remote_text),
  telecommuting_field_yes = sum(roles$telecommuting_ok),
  both_yes = counts[1L], text_yes_flag_no = counts[2L],
  flag_yes_no_text = counts[3L], neither_positive = counts[4L],
  union_discovery_queue = sum(roles$discovery_candidate),
  explicit_remote_conflicts = sum(roles$explicit_remote_conflict),
  one_signal_only = sum(roles$one_signal_only),
  remote_text_disagree_percent = 100 * counts[2L] / sum(roles$remote_text),
  worldwide_in_title_or_location = sum(roles$worldwide_text),
  oldest_posting = min(roles$posted_date), newest_posting = max(roles$posted_date),
  requests_in_saved_refresh = length(manifest$requests$url),
  scope_note = "Advertised field statements, not verified remote availability or an estimate of the whole labor market."
)
# jsonlite may simplify an array of request records to a data frame.
if (is.null(manifest$requests$url)) summary$requests_in_saved_refresh <- length(manifest$requests)
write_json(summary, file.path(results_dir, "summary.json"), pretty = TRUE, auto_unbox = TRUE, digits = 8)
capture.output(sessionInfo(), file = file.path(results_dir, "sessionInfo.txt"))

# One substantive figure: the overlap of two independently scraped signals.
labels <- c("Remote text +\nflag says OK", "Remote text +\nflag says no", "Flag says OK +\nno remote text", "Neither gives a\npositive remote signal")
colours <- c("#1D5C83", "#B45C2A", "#79679E", "#8B98A5")
png(file.path(results_dir, "figures", "remote_signals.png"), width = 1800, height = 1000,
    res = 200, pointsize = 12, type = "cairo")
par(mar = c(4.8, 10.4, 4.3, 1.8), family = "sans", fg = "#263442", col.axis = "#4B5563")
upper <- max(counts) + 1.7
plot.new()
plot.window(xlim = c(0, upper), ylim = c(0.45, 4.55), xaxs = "i", yaxs = "i")
ticks <- seq.int(0, max(counts))
abline(v = ticks, col = "#E7E9ED", lwd = 0.8)
positions <- 4:1
rect(0, positions - 0.3, counts, positions + 0.3, col = colours, border = NA)
text(-0.18, positions, labels = labels, adj = 1, xpd = NA, cex = 0.95)
text(counts + 0.15, positions, labels = counts, adj = 0, font = 2, cex = 1.05)
axis(1, at = ticks, tck = -0.015, lwd = 0, lwd.ticks = 1, col.ticks = "#AAB2BC")
mtext("Number of distinct employer-title entries", side = 1, line = 2.6, cex = 0.95)
mtext("Two remote-job signals give different shortlists", side = 3, line = 2.3,
      adj = 0, font = 2, cex = 1.15)
mtext(sprintf("Python.org snapshot: %s | %d employer-title entries", manifest$capture_date_utc, nrow(roles)),
      side = 3, line = 0.8, adj = 0, cex = 0.87, col = "#56616D")
dev.off()

# Generate the case table from the same extracted records. Locations and
# checkbox fields are factual data; the action column is an interpretation.
case_companies <- c("tem", "Adzuna", "ActivePrime, Inc.", "Reef Technologies")
case_rows <- lapply(case_companies, function(company) {
  d <- roles[roles$company == company, ]
  if (nrow(d) == 0L) stop(paste("Article example absent from snapshot:", company))
  if (company == "Reef Technologies") d <- d[grepl("^Lead", d$title), ]
  d[1L, ]
})
case_rows <- do.call(rbind, case_rows)
if (!identical(case_rows$telecommuting_ok, c(TRUE, FALSE, FALSE, FALSE))) {
  stop("Example fields changed: review the case commentary before generating the article.")
}
actions <- c("Check UK/EU eligibility.",
             "Check hours; clarify the flag.",
             "Clarify the flag; confirm countries.",
             "Confirm eligible countries.")
case_table <- c("| Example | Title/location signal | Detail field | First check |",
                "| --- | --- | --- | --- |")
for (i in seq_len(nrow(case_rows))) {
  d <- case_rows[i, ]
  signal <- if (d$company == "ActivePrime, Inc.") "Title says fully remote worldwide" else d$location
  # Shorten repeated location tokens without changing the geographic claim.
  if (d$company == "tem") signal <- "Remote (UK / EU)"
  if (d$company == "Adzuna") signal <- "Remote, within 2 hours of London time"
  case_table <- c(case_table, sprintf("| [%s](%s) | %s | %s | %s |",
    d$company, d$source_url, signal, d$telecommuting_field, actions[i]))
}
writeLines(case_table, file.path(results_dir, "cases.txt"), useBytes = TRUE)

template <- file.path(root, "code", "article_template.txt")
if (file.exists(template)) {
  article <- paste(readLines(template, warn = FALSE), collapse = "\n")
  replacements <- c(
    SNAPSHOT_DATE = manifest$capture_date_utc,
    RAW = nrow(postings), N = nrow(roles), DUPLICATES = sum(!postings$keep_for_analysis),
    REMOTE_TEXT = sum(roles$remote_text), FLAG_YES = sum(roles$telecommuting_ok),
    BOTH = counts[1L], TEXT_ONLY = counts[2L], FLAG_ONLY = counts[3L], NEITHER = counts[4L],
    UNION = sum(roles$discovery_candidate), CONFLICTS = sum(roles$explicit_remote_conflict),
    PERCENT_TEXT_ONLY = sprintf("%.0f", 100 * counts[2L] / sum(roles$remote_text)),
    WORLDWIDE = sum(roles$worldwide_text), CASE_TABLE = paste(case_table, collapse = "\n")
  )
  for (name in names(replacements)) article <- gsub(paste0("@@", name, "@@"),
    as.character(replacements[[name]]), article, fixed = TRUE)
  if (grepl("@@[A-Z_]+@@", article)) stop("Unfilled article token.")
  writeLines(article, file.path(root, "blog2.qmd"), useBytes = TRUE)
}
cat(toJSON(summary, pretty = TRUE, auto_unbox = TRUE), "\n")
