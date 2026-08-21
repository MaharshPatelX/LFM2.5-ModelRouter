# Synthetic xRouteBench Fixture

`synthetic_routing_sample.jsonl` is authored specifically for repository tests.
It follows one observed xRouteBench routing schema but contains no copied
upstream prompts, responses, model IDs, or annotations.

The real xRouteBench files remain under ignored `data/raw/` paths. They must not
be committed because the pinned upstream revision does not declare a dataset
license or include a license file.
