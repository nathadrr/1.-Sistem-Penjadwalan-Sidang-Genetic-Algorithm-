import itertools

SLOT_COUNT = 45
LOCKED_START = 9
LOCKED_END = 27
DEFAULT_GENE_COUNT = 4


class Chromosome:
    def __init__(self, genes=None, gene_count=DEFAULT_GENE_COUNT):
        if genes is None:
            self.genes = [0 for _ in range(gene_count)]
        else:
            self.genes = [int(g) for g in genes]

    def __str__(self):
        return f"[{', '.join(str(g) for g in self.genes)}]"

    def __repr__(self):
        return self.__str__()


class Individual:
    def __init__(self, chromosomes=None, gene_count=DEFAULT_GENE_COUNT):
        self.gene_count = gene_count
        if chromosomes is None:
            self.chromosomes = [Chromosome(gene_count=gene_count) for _ in range(SLOT_COUNT)]
        else:
            if len(chromosomes) != SLOT_COUNT:
                raise ValueError(f"Individual must have exactly {SLOT_COUNT} chromosomes")
            self.chromosomes = chromosomes

    def to_array(self):
        return [chromosome.genes.copy() for chromosome in self.chromosomes]

    def __str__(self):
        return f"Individual with {len(self.chromosomes)} chromosomes"


def create_empty_individual(gene_count=DEFAULT_GENE_COUNT):
    return Individual([Chromosome([0 for _ in range(gene_count)]) for _ in range(SLOT_COUNT)], gene_count=gene_count)


def build_parent_from_array(parent_array):
    """Convert a nested array of 45 chromosomes into an Individual."""
    if len(parent_array) != SLOT_COUNT:
        raise ValueError(f"Parent must contain exactly {SLOT_COUNT} chromosomes")

    chromosomes = []
    for genes in parent_array:
        gene_list = [int(g) for g in genes]
        chromosomes.append(Chromosome(gene_list, gene_count=len(gene_list)))

    return Individual(chromosomes=chromosomes, gene_count=len(chromosomes[0].genes))


def normalize_parents(parents):
    """Accept either Individual objects or nested arrays and return a list of Individuals."""
    normalized = []
    for parent in parents:
        if isinstance(parent, Individual):
            normalized.append(parent)
        elif isinstance(parent, list):
            normalized.append(build_parent_from_array(parent))
        else:
            raise TypeError("Each parent must be an Individual or a nested list")
    return normalized


def parse_numbers_from_line(line):
    cleaned = line.replace('\t', ' ').replace(',', ' ').replace('[', ' ').replace(']', ' ')
    return [int(part) for part in cleaned.split() if part.lstrip('-').isdigit()]


def load_parents_from_file(filename="parents.txt"):
    """Load parents from the text file. Supports both 3-value and 4-value chromosome formats."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except Exception as exc:
        print(f"Error loading parents from file: {exc}")
        return []

    parent_blocks = {}
    current_parent = None
    current_numbers = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('P') and '=' in line:
            if current_parent is not None:
                parent_blocks[current_parent] = current_numbers
            current_parent = line.split('=')[0].strip()
            current_numbers = []
            line = line.split('[', 1)[1] if '[' in line else ''
        elif line == ']':
            if current_parent is not None:
                parent_blocks[current_parent] = current_numbers
                current_parent = None
                current_numbers = []
            continue

        if current_parent is not None:
            current_numbers.extend(parse_numbers_from_line(line))

    if current_parent is not None:
        parent_blocks[current_parent] = current_numbers

    if not parent_blocks:
        return []

    parents = []
    for parent_name in sorted(parent_blocks, key=lambda name: int(name[1:])):
        numbers = parent_blocks[parent_name]
        if not numbers:
            continue
        gene_count = len(numbers) // SLOT_COUNT if len(numbers) % SLOT_COUNT == 0 else DEFAULT_GENE_COUNT
        chromosomes = []
        for slot_idx in range(SLOT_COUNT):
            start = slot_idx * gene_count
            end = start + gene_count
            genes = numbers[start:end]
            if len(genes) < gene_count:
                genes = genes + [0] * (gene_count - len(genes))
            chromosomes.append(Chromosome(genes, gene_count=gene_count))
        parents.append(Individual(chromosomes=chromosomes, gene_count=gene_count))

    return parents


def crossover_and_fill(parent1, parent2, locked_start=LOCKED_START, locked_end=LOCKED_END):
    """Create two children from two parents using a locked middle section."""
    child1 = create_empty_individual(gene_count=parent1.gene_count)
    child2 = create_empty_individual(gene_count=parent2.gene_count)
    locked_indices = list(range(locked_start, locked_end))

    for idx in locked_indices:
        child1.chromosomes[idx] = Chromosome(parent1.chromosomes[idx].genes.copy(), gene_count=parent1.gene_count)
        child2.chromosomes[idx] = Chromosome(parent2.chromosomes[idx].genes.copy(), gene_count=parent2.gene_count)

    unlocked_indices = [i for i in range(SLOT_COUNT) if i not in set(locked_indices)]
    for slot_idx in unlocked_indices:
        child1.chromosomes[slot_idx] = Chromosome(parent2.chromosomes[slot_idx].genes.copy(), gene_count=parent2.gene_count)
        child2.chromosomes[slot_idx] = Chromosome(parent1.chromosomes[slot_idx].genes.copy(), gene_count=parent1.gene_count)

    return child1, child2


def generate_all_children(parents):
    """Generate all non-repeating parent-pair children and return them as a nested array."""
    normalized_parents = normalize_parents(parents)
    if len(normalized_parents) < 2:
        raise ValueError("At least 2 parents are required to generate children")

    all_children = []
    for i, j in itertools.combinations(range(len(normalized_parents)), 2):
        parent1 = normalized_parents[i]
        parent2 = normalized_parents[j]
        child1, child2 = crossover_and_fill(parent1, parent2)
        all_children.append(child1.to_array())
        all_children.append(child2.to_array())
    return all_children


if __name__ == "__main__":
    print("Loading parents from file...")
    parents = load_parents_from_file()

    if parents:
        all_children = generate_all_children(parents)
        print(f"Generated {len(all_children)} children from {len(parents)} parents.")
        print("Example child structure:")
        print(all_children[0][0])
        print("First 3 chromosomes of the first child:")
        print(all_children[0][:3])
    else:
        print("No parents were loaded from file. Import this module and call generate_all_children(parents) with your parent data.")
