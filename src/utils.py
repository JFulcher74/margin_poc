def get_worst_confidence(conf_list: list) -> str:
    """Returns the lowest confidence from a list of confidence scores."""
    mapping = {'Low': 1, 'Med': 2, 'High': 3}
    reverse_mapping = {1: 'Low', 2: 'Med', 3: 'High'}
    
    scores = [mapping.get(c, 1) for c in conf_list]
    if not scores:
        return 'Low'
    
    return reverse_mapping[min(scores)]