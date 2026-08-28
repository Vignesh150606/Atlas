from app.retrieval.semantic_match import stem, relevance_score, build_term_weights


def test_stem_strips_common_suffixes():
    assert stem("classes") == "class"
    assert stem("running") == "runn"
    assert stem("tasked") == "task"


def test_stem_does_not_over_strip_short_words():
    # "is" (len 2) must not be reduced to nothing / a 0-3 char stem that
    # would collide with unrelated words.
    assert stem("is") == "is"
    assert stem("bus") == "bus"  # ends in "s" but stripping would leave "bu" (< 3 chars)


def test_exact_keyword_match_scores_full_credit():
    score = relevance_score("Math class at 9am", ["math"])
    assert score == 1.0


def test_stem_near_miss_scores_partial_credit_not_zero():
    # "tasked" and "tasks" share a stem ("task") but neither is a substring
    # of the other, so this genuinely exercises the stem-fallback path
    # rather than plain substring containment.
    exact = relevance_score("I have a task today", ["task"])
    near_miss = relevance_score("Everything is tasked out for today", ["tasks"])
    unrelated = relevance_score("Nothing relevant here", ["tasks"])
    assert near_miss < exact
    assert near_miss > unrelated
    assert unrelated == 0.0


def test_no_keywords_scores_zero():
    assert relevance_score("anything", []) == 0.0


def test_multiple_keywords_average_correctly():
    # One exact hit, one total miss, out of two keywords -> 0.5.
    score = relevance_score("I love pizza", ["pizza", "sushi"])
    assert score == 0.5


def test_build_term_weights_favors_rare_terms():
    corpus = [
        "I have a math class at 9am",
        "I have a math class at 2pm",
        "I have a chemistry lab at 3pm",
    ]
    weights = build_term_weights(corpus)
    # "math" appears in 2/3 docs, "chemistry" in 1/3 - chemistry is rarer
    # and should be weighted higher (more informative signal).
    assert weights[stem("chemistry")] > weights[stem("math")]


def test_relevance_score_uses_term_weights_when_supplied():
    corpus = [
        "task reminder for today",
        "task reminder for tomorrow",
        "quantum physics assignment due",
    ]
    weights = build_term_weights(corpus)
    # "task" is common (low weight), "quantum" is rare (high weight) -
    # a single rare-keyword hit should outscore a single common-keyword hit.
    task_score = relevance_score("task reminder for today", ["task"], term_weights=weights)
    quantum_score = relevance_score("quantum physics assignment due", ["quantum"], term_weights=weights)
    assert quantum_score >= task_score
