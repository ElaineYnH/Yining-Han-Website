args <- commandArgs(trailingOnly = TRUE)

if (!requireNamespace("ipumsr", quietly = TRUE)) {
  stop("Install ipumsr first: install.packages('ipumsr')")
}

if (length(args) == 1L) {
  ddi_file <- normalizePath(args[1], mustWork = TRUE)
  script_arg <- grep("^--file=", commandArgs(), value = TRUE)[1]
  post_dir <- dirname(normalizePath(sub("^--file=", "", script_arg),
                                    mustWork = TRUE))
} else if (length(args) == 0L && interactive()) {
  message("First, select the IPUMS CPS DDI .xml codebook.")
  ddi_file <- normalizePath(file.choose(), mustWork = TRUE)
  message("Next, select blog3.qmd inside your website's blog/posts/post3 folder.")
  post_file <- normalizePath(file.choose(), mustWork = TRUE)
  if (basename(post_file) != "blog3.qmd") {
    stop("The second file must be blog/posts/post3/blog3.qmd")
  }
  post_dir <- dirname(post_file)
} else {
  stop("Usage: Rscript blog/posts/post3/prepare_cps.R /path/to/cps_extract.xml")
}

data <- ipumsr::read_ipums_micro(ddi_file, verbose = FALSE)
required <- c("YEAR", "MONTH", "AGE", "EDUC", "EMPSTAT", "WTFINL")
missing <- setdiff(required, names(data))

if (length(missing) > 0L) {
  stop("Missing extract variables: ", paste(missing, collapse = ", "))
}

data <- as.data.frame(lapply(data[required], as.numeric))
years <- c(2019, 2020, 2025)
data <- subset(data, YEAR %in% years & MONTH == 4 & AGE >= 25 & AGE <= 64 &
                 is.finite(WTFINL) & WTFINL > 0)

if (!setequal(unique(data$YEAR), years)) {
  stop("The extract must contain the April 2019, 2020, and 2025 basic monthly samples.")
}

data$education <- NA_character_
data$education[data$EDUC >= 2 & data$EDUC <= 71] <- "Less than high school"
data$education[data$EDUC == 73] <- "High school diploma"
data$education[data$EDUC >= 80 & data$EDUC <= 110] <- "Some college / associate"
data$education[data$EDUC >= 111 & data$EDUC <= 125] <- "Bachelor's or higher"

# The first digit of IPUMS EMPSTAT distinguishes employed, unemployed, and NILF.
data$status <- floor(data$EMPSTAT / 10)
data <- subset(data, !is.na(education) & status %in% 1:3)

groups <- c("Less than high school", "High school diploma",
            "Some college / associate", "Bachelor's or higher")

summarize_group <- function(year, group) {
  rows <- data[data$YEAR == year & data$education == group, ]
  population <- sum(rows$WTFINL)
  employed <- sum(rows$WTFINL[rows$status == 1])
  unemployed <- sum(rows$WTFINL[rows$status == 2])
  out_lf <- sum(rows$WTFINL[rows$status == 3])
  labor_force <- employed + unemployed

  if (nrow(rows) == 0L || population <= 0 || labor_force <= 0) {
    stop("No valid weighted observations for ", year, " / ", group)
  }

  data.frame(
    year = year,
    education = group,
    n = nrow(rows),
    population = population,
    employed = employed,
    unemployed = unemployed,
    out_lf = out_lf,
    unemployment_rate = unemployed / labor_force,
    employment_pop_rate = employed / population,
    participation_rate = labor_force / population
  )
}

summary <- do.call(rbind, lapply(years, function(year) {
  do.call(rbind, lapply(groups, function(group) summarize_group(year, group)))
}))

output_dir <- file.path(post_dir, "data")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
output_file <- file.path(output_dir, "cps_education_summary.csv")
write.csv(summary, output_file, row.names = FALSE)
message("Saved weighted aggregate results: ", output_file)
