.PHONY: report watch results

# The report uses Lato, the template's font, from report/fonts.
TYPST_FLAGS = --root . --font-path report/fonts

report:
	mkdir -p output/pdf
	typst compile $(TYPST_FLAGS) report/main.typ output/pdf/assignment-3.pdf

watch:
	mkdir -p output/pdf
	typst watch $(TYPST_FLAGS) report/main.typ output/pdf/assignment-3.pdf

# The program output shown in the report: the EDA and each Part 2 task.
results:
	mkdir -p report/results
	uv run python eda.py > report/results/eda.txt
	for n in 1 2 3 4 5 6 7 8 9 10; do \
		uv run python queries.py $$n > report/results/task$$n.txt; \
	done
