# Rebuild the existing three plots and the revised interpretation from the saved
# weighted summary. No raw IPUMS data or network access is required.
# Rscript blog/posts/post3/code/build_from_summary.R
file_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
if (length(file_arg) != 1L) stop("Run this file with Rscript.")
root <- dirname(dirname(normalizePath(sub("^--file=", "", file_arg))))

library(ggplot2)

locations <- file.path(root, "data", "cps_education_summary.csv")
found <- locations[file.exists(locations)]
if (length(found) == 0) {
  stop("Run prepare_cps.R on an IPUMS CPS extract before rendering this post.")
}

results <- read.csv(found[1], stringsAsFactors = FALSE)
required <- c("year", "education", "population", "employed", "unemployed",
              "out_lf", "unemployment_rate", "employment_pop_rate",
              "participation_rate")
stopifnot(all(required %in% names(results)), nrow(results) == 12L,
          setequal(results$year, c(2019, 2020, 2025)),
          all(is.finite(results$unemployment_rate)),
          all(abs(results$population - results$employed - results$unemployed -
                  results$out_lf) < 1e-5 * results$population))

groups <- c("Less than high school", "High school diploma",
            "Some college / associate", "Bachelor's or higher")
results$education <- factor(results$education, levels = groups)
stopifnot(!anyNA(results$education))
stopifnot(!anyDuplicated(results[c("year", "education")]),
          all(results$population > 0),
          all(abs(results$unemployment_rate - results$unemployed /
                    (results$employed + results$unemployed)) < 1e-9),
          all(abs(results$employment_pop_rate - results$employed /
                    results$population) < 1e-9),
          all(abs(results$participation_rate -
                    (results$employed + results$unemployed) /
                    results$population) < 1e-9))

pct <- function(x) sprintf("%.1f%%", 100 * x)
pp <- function(x) sprintf("%.1f", 100 * x)
value <- function(year, group, column) {
  x <- results[results$year == year & results$education == group, column]
  stopifnot(length(x) == 1L)
  x
}

gap2025 <- value(2025, "Bachelor's or higher", "employment_pop_rate") -
  value(2025, "Less than high school", "employment_pop_rate")

colors <- c("Less than high school" = "#BC4B51",
            "High school diploma" = "#DC8840",
            "Some college / associate" = "#3C8990",
            "Bachelor's or higher" = "#415DA0")
plot_theme <- theme_minimal(base_size = 12) +
  theme(panel.grid.minor = element_blank(), legend.position = "bottom",
        plot.title.position = "plot", plot.caption = element_text(hjust = 0))

figure_dir <- file.path(dirname(found[1]), "..", "figures")
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)

p1 <- ggplot(results, aes(year, unemployment_rate, color = education,
                          group = education)) +
  geom_line(linewidth = 1) +
  geom_point(size = 2.8) +
  scale_x_continuous(breaks = c(2019, 2020, 2025)) +
  scale_y_continuous(labels = scales::label_percent(accuracy = 1),
                     limits = c(0, NA), expand = expansion(mult = c(0, .08))) +
  scale_color_manual(values = colors, name = "Education") +
  labs(x = NULL, y = "Unemployed / labor force",
       title = "The labor-market shock differed by education") +
  plot_theme
ggsave(file.path(figure_dir, "unemployment.png"), p1,
       width = 8.5, height = 5, dpi = 180, bg = "white")

p2 <- ggplot(results, aes(year, employment_pop_rate, color = education,
                          group = education)) +
  geom_line(linewidth = 1) +
  geom_point(size = 2.8) +
  scale_x_continuous(breaks = c(2019, 2020, 2025)) +
  scale_y_continuous(labels = scales::label_percent(accuracy = 1),
                     limits = c(0, 1)) +
  scale_color_manual(values = colors, name = "Education") +
  labs(x = NULL, y = "Employed / population",
       title = "A broader measure: the share of adults working") +
  plot_theme
ggsave(file.path(figure_dir, "employment.png"), p2,
       width = 8.5, height = 5, dpi = 180, bg = "white")

latest <- subset(results, year == 2025)
nonemployment <- rbind(
  data.frame(education = latest$education, status = "Unemployed",
             share = latest$unemployed / latest$population),
  data.frame(education = latest$education, status = "Outside labor force",
             share = latest$out_lf / latest$population)
)
p3 <- ggplot(nonemployment, aes(education, share, fill = status)) +
  geom_col(width = .65) +
  coord_flip() +
  scale_y_continuous(labels = scales::label_percent(accuracy = 1),
                     limits = c(0, .5), expand = expansion(mult = c(0, .03))) +
  scale_fill_manual(values = c("Unemployed" = "#BC4B51",
                               "Outside labor force" = "#768594"), name = NULL) +
  labs(x = NULL, y = "Share of group population",
       title = "Nonemployment has two components") +
  plot_theme
ggsave(file.path(figure_dir, "nonemployment.png"), p3,
       width = 8.5, height = 5, dpi = 180, bg = "white")

# Use the same population denominator for both parts of the employment gap.
decomposition <- data.frame(
  year = latest$year,
  education = as.character(latest$education),
  employment_share = latest$employed / latest$population,
  unemployed_population_share = latest$unemployed / latest$population,
  outside_labor_force_share = latest$out_lf / latest$population,
  participation_share = (latest$employed + latest$unemployed) / latest$population
)
decomposition <- decomposition[match(groups, decomposition$education), ]
stopifnot(all(abs(rowSums(decomposition[c("employment_share",
  "unemployed_population_share", "outside_labor_force_share")]) - 1) < 1e-9))

low <- groups[1]
high <- groups[4]
u_pop <- function(group) value(2025, group, "unemployed") /
  value(2025, group, "population")
nilf <- function(group) value(2025, group, "out_lf") /
  value(2025, group, "population")
nilf_gap <- nilf(low) - nilf(high)
u_pop_gap <- u_pop(low) - u_pop(high)
gap2019 <- value(2019, high, "employment_pop_rate") -
  value(2019, low, "employment_pop_rate")
stopifnot(abs(gap2025 - nilf_gap - u_pop_gap) < 1e-9,
          all(vapply(groups, function(group)
            value(2025, group, "employment_pop_rate") >=
            value(2019, group, "employment_pop_rate"), logical(1))))

numbers <- c(
  LOW_U_2019 = value(2019, low, "unemployment_rate"),
  LOW_U_2020 = value(2020, low, "unemployment_rate"),
  HIGH_U_2019 = value(2019, high, "unemployment_rate"),
  HIGH_U_2020 = value(2020, high, "unemployment_rate"),
  LOW_U_2025 = value(2025, low, "unemployment_rate"),
  HIGH_U_2025 = value(2025, high, "unemployment_rate"),
  HIGH_E_2025 = value(2025, high, "employment_pop_rate"),
  LOW_E_2025 = value(2025, low, "employment_pop_rate"),
  E_GAP_2025 = gap2025,
  E_GAP_2019 = gap2019,
  LOW_NILF = nilf(low),
  LOW_U_POP = u_pop(low),
  HIGH_NILF = nilf(high),
  HIGH_U_POP = u_pop(high),
  LOW_PARTICIPATION = value(2025, low, "participation_rate"),
  HIGH_PARTICIPATION = value(2025, high, "participation_rate"),
  NILF_GAP = nilf_gap,
  U_POP_GAP = u_pop_gap,
  NILF_FRACTION = nilf_gap / gap2025
)
point_metrics <- c("E_GAP_2025", "E_GAP_2019", "NILF_GAP", "U_POP_GAP")
display <- vapply(numbers, pct, character(1))
display[point_metrics] <- vapply(numbers[point_metrics], pp, character(1))
display["NILF_FRACTION"] <- sprintf("%.0f", 100 * numbers["NILF_FRACTION"])

result_dir <- file.path(root, "results")
dir.create(result_dir, recursive = TRUE, showWarnings = FALSE)
write.csv(decomposition, file.path(result_dir, "decomposition_2025.csv"),
          row.names = FALSE)
write.csv(data.frame(metric = names(numbers), value = 100 * unname(numbers),
  unit = ifelse(names(numbers) %in% point_metrics, "percentage_points", "percent")),
  file.path(result_dir, "story_numbers.csv"), row.names = FALSE)
writeLines(capture.output(sessionInfo()), file.path(result_dir, "sessionInfo.txt"))

article <- readLines(file.path(root, "code", "article_template.txt"), warn = FALSE)
for (key in names(display)) {
  token <- paste0("@@", key, "@@")
  stopifnot(any(grepl(token, article, fixed = TRUE)))
  article <- gsub(token, display[[key]], article, fixed = TRUE)
}
stopifnot(!any(grepl("@@[A-Z_0-9]+@@", article)))
writeLines(article, file.path(root, "blog3.qmd"), useBytes = TRUE)
message("Rebuilt three figures, article, and decomposition from the unchanged summary.")
