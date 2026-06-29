import importlib
import subprocess
import sys


def install_and_import(packages):
    for pkg in packages:
        try:
            importlib.import_module(pkg)
        except ImportError:
            print(f"Package '{pkg}' not found; installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_and_import(["streamlit", "pandas", "openpyxl"])

import streamlit as st
import pandas as pd
import random
import os
import itertools


try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except Exception:
    def get_script_run_ctx():
        return None

if __name__ == "__main__":
    if get_script_run_ctx() is None:
        script_path = os.path.abspath(__file__)
        print("This app should be run with 'streamlit run'.")
        print(f"Run: streamlit run {script_path}")
        sys.exit(0)

SLOT_COUNT = 90
LOCKED_RANGES = [(9, 27), (54, 72)]  
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
    if len(parent_array) != SLOT_COUNT:
        raise ValueError(f"Parent must contain exactly {SLOT_COUNT} chromosomes")
    chromosomes = []
    for genes in parent_array:
        gene_list = [int(g) for g in genes]
        chromosomes.append(Chromosome(gene_list, gene_count=len(gene_list)))
    return Individual(chromosomes=chromosomes, gene_count=len(chromosomes[0].genes))


def normalize_parents(parents):
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


def build_student_queue(parent, locked_student_ids):
    queue = []
    seen = set()
    for chromosome in parent.chromosomes:
        for student_id in chromosome.genes:
            if student_id == 0:
                continue
            if student_id in seen:
                continue
            if student_id in locked_student_ids:
                continue
            seen.add(student_id)
            queue.append(int(student_id))
    return queue


def crossover_and_fill(parent1, parent2, locked_ranges=None, mahasiswa=None, availability=None, debug_list=None):
    child1 = create_empty_individual(gene_count=parent1.gene_count)
    child2 = create_empty_individual(gene_count=parent2.gene_count)

    if locked_ranges is None:
        locked_ranges = LOCKED_RANGES

    locked_indices = set()
    for start, end in locked_ranges:
        locked_indices.update(range(start, end))

    for idx in sorted(locked_indices):
        child1.chromosomes[idx] = Chromosome(parent1.chromosomes[idx].genes.copy(), gene_count=parent1.gene_count)
        child2.chromosomes[idx] = Chromosome(parent2.chromosomes[idx].genes.copy(), gene_count=parent2.gene_count)

    locked_student_ids = {
        int(student_id)
        for idx in sorted(locked_indices)
        for student_id in child1.chromosomes[idx].genes
        if student_id != 0
    }

    child1_schedule = [chromosome.genes.copy() for chromosome in child1.chromosomes]
    child2_schedule = [chromosome.genes.copy() for chromosome in child2.chromosomes]

    child1_queue = build_student_queue(parent2, locked_student_ids)
    child2_queue = build_student_queue(parent1, {
        int(student_id)
        for idx in sorted(locked_indices)
        for student_id in child2.chromosomes[idx].genes
        if student_id != 0
    })

    child1_failure = None
    for student_id in child1_queue:
        placed = False
        for slot_number in range(1, SLOT_COUNT + 1):
            slot_idx = slot_number - 1
            if slot_idx in locked_indices:
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (locked)")
                continue
            if mahasiswa is not None and availability is not None:
                if not check_availability(student_id, slot_number, mahasiswa, availability):
                    if debug_list is not None:
                        debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (availability)")
                    continue
            room = get_empty_room(child1_schedule, slot_idx)
            if room is None:
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (no empty room)")
                continue
            if mahasiswa is not None and availability is not None and not check_conflict(child1_schedule, slot_idx, student_id, mahasiswa):
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (conflict)")
                continue
            child1_schedule[slot_idx][room] = student_id
            child1.chromosomes[slot_idx] = Chromosome(child1_schedule[slot_idx].copy(), gene_count=parent1.gene_count)
            if debug_list is not None:
                debug_list.append(f"child1: student {student_id} placed slot {slot_number} room {room}")
            placed = True
            break
        if not placed:
            child1_failure = f"Student {student_id} could not be placed"
            if debug_list is not None:
                debug_list.append(f"child1: {child1_failure}")
            break

    child2_failure = None
    for student_id in child2_queue:
        placed = False
        for slot_number in range(1, SLOT_COUNT + 1):
            slot_idx = slot_number - 1
            if slot_idx in locked_indices:
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (locked)")
                continue
            if mahasiswa is not None and availability is not None:
                if not check_availability(student_id, slot_number, mahasiswa, availability):
                    if debug_list is not None:
                        debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (availability)")
                    continue
            room = get_empty_room(child2_schedule, slot_idx)
            if room is None:
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (no empty room)")
                continue
            if mahasiswa is not None and availability is not None and not check_conflict(child2_schedule, slot_idx, student_id, mahasiswa):
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (conflict)")
                continue
            child2_schedule[slot_idx][room] = student_id
            child2.chromosomes[slot_idx] = Chromosome(child2_schedule[slot_idx].copy(), gene_count=parent2.gene_count)
            if debug_list is not None:
                debug_list.append(f"child2: student {student_id} placed slot {slot_number} room {room}")
            placed = True
            break
        if not placed:
            child2_failure = f"Student {student_id} could not be placed"
            if debug_list is not None:
                debug_list.append(f"child2: {child2_failure}")
            break

    return child1, child2, child1_failure, child2_failure


def generate_all_children(parents, mahasiswa=None, availability=None, error_callback=None, debug=False):
    normalized_parents = normalize_parents(parents)
    if len(normalized_parents) < 2:
        raise ValueError("At least 2 parents are required to generate children")

    all_children = []
    failed_children = []
    for i, j in itertools.combinations(range(len(normalized_parents)), 2):
        parent1 = normalized_parents[i]
        parent2 = normalized_parents[j]
        debug_list = [] if debug else None
        child1, child2, child1_failure, child2_failure = crossover_and_fill(
            parent1,
            parent2,
            mahasiswa=mahasiswa,
            availability=availability,
            debug_list=debug_list,
        )

        if child1_failure is not None:
            failed_children.append((i, j, 1, child1_failure))
            if error_callback is not None:
                error_callback(f"Child 1 from parents {i+1} and {j+1} could not be made: {child1_failure}")
        else:
            entry = {
                "parents": (i + 1, j + 1),
                "child_index": 1,
                "schedule": child1.to_array(),
            }
            if debug and debug_list is not None:
                entry["debug"] = [m for m in debug_list]
            all_children.append(entry)

        if child2_failure is not None:
            failed_children.append((i, j, 2, child2_failure))
            if error_callback is not None:
                error_callback(f"Child 2 from parents {i+1} and {j+1} could not be made: {child2_failure}")
        else:
            entry = {
                "parents": (i + 1, j + 1),
                "child_index": 2,
                "schedule": child2.to_array(),
            }
            if debug and debug_list is not None:
                entry["debug"] = [m for m in debug_list]
            all_children.append(entry)

    return all_children, failed_children

def swap_mutation(child_schedule, mahasiswa, availability, mutation_rate=0.05):
    """
    Melakukan swap mutation pada schedule (list of lists) berdasarkan mutation_rate.
    Mengikuti aturan gambar: coba hingga 3x jika invalid, batalkan jika tetap gagal.
    """
    if random.random() > mutation_rate:
        return child_schedule, False, "Tidak terkena probabilitas mutasi"

    import copy
    mutated_schedule = copy.deepcopy(child_schedule)
    
    locked_indices = set()
    for start, end in LOCKED_RANGES:
        locked_indices.update(range(start, end))
        
    available_positions = []
    for slot_idx in range(SLOT_COUNT):
        if slot_idx not in locked_indices:
            for room_idx in range(4):
                available_positions.append((slot_idx, room_idx))

    for attempt in range(1, 4):
        if len(available_positions) < 2:
            return child_schedule, False, "Posisi tidak cukup untuk swap"
            
        pos1, pos2 = random.sample(available_positions, 2)
        slot1, room1 = pos1
        slot2, room2 = pos2
        
        mhs1 = mutated_schedule[slot1][room1]
        mhs2 = mutated_schedule[slot2][room2]
        
        if mhs1 == 0 and mhs2 == 0:
            continue
            
        mutated_schedule[slot1][room1] = mhs2
        mutated_schedule[slot2][room2] = mhs1
        
        valid = True
        
        if mhs2 != 0:
            if not check_availability(mhs2, slot1 + 1, mahasiswa, availability):
                valid = False
            mutated_schedule[slot1][room1] = 0
            if not check_conflict(mutated_schedule, slot1, mhs2, mahasiswa):
                valid = False
            mutated_schedule[slot1][room1] = mhs2
            
        if mhs1 != 0 and valid:
            if not check_availability(mhs1, slot2 + 1, mahasiswa, availability):
                valid = False
            mutated_schedule[slot2][room2] = 0
            if not check_conflict(mutated_schedule, slot2, mhs1, mahasiswa):
                valid = False
            mutated_schedule[slot2][room2] = mhs1
            
        if valid:
            return mutated_schedule, True, f"Berhasil mutasi (Percobaan ke-{attempt}): Swap Slot {slot1+1} Rm {room1} <-> Slot {slot2+1} Rm {room2}"
        else:
            mutated_schedule[slot1][room1] = mhs1
            mutated_schedule[slot2][room2] = mhs2

    return child_schedule, False, "Gagal mutasi: Tidak menemukan slot valid setelah 3x Re-Mutation (Mutasi Dibatalkan)"

def preprocessing_availability(df):
    availability = {}
    for dosen in df.columns[1:]:
        dosen = dosen.strip()
        slot_tersedia = set()
        for _, row in df.iterrows():
            if row[dosen] == 1:
                slot_tersedia.add(int(row["id_slot"]))
        availability[dosen] = slot_tersedia
    return availability


def preprocessing_mahasiswa(df):
    mahasiswa = {}
    for _, row in df.iterrows():
        dosen = set()
        for kolom in ["dosbing1", "dosbing2", "dosenpenguji1", "dosenpenguji2"]:
            if pd.notna(row[kolom]):
                dosen.add(str(row[kolom]).strip())
        mahasiswa[int(row["id_mhs"])] = {"dosen": dosen}
    return mahasiswa


def check_availability(id_mhs, slot, mahasiswa, availability):
    dosen = mahasiswa[id_mhs]["dosen"]
    for d in dosen:
        if slot not in availability[d]:
            return False
    return True


def check_conflict(chromosome, slot, id_mhs, mahasiswa):
    dosen_baru = mahasiswa[id_mhs]["dosen"]
    for mhs in chromosome[slot]:
        if mhs == 0:
            continue
        dosen_lama = mahasiswa[mhs]["dosen"]
        if dosen_baru & dosen_lama:
            return False
    return True


def get_empty_room(chromosome, slot):
    for r in range(4):
        if chromosome[slot][r] == 0:
            return r
    return None

def jumlah_slot_valid(id_mhs, mahasiswa, availability):
    dosen = mahasiswa[id_mhs]["dosen"]

    slot = None
    for d in dosen:
        if slot is None:
            slot = availability[d].copy()
        else:
            slot &= availability[d]

    return len(slot)

def generate_initial_population(population_size, mahasiswa, availability, max_retries=500):
    population = []
    jumlah_slot = SLOT_COUNT
    jumlah_ruangan = 4
    daftar_mahasiswa = sorted(
        mahasiswa.keys(),
        key=lambda m: jumlah_slot_valid(m, mahasiswa, availability)
    )

    progress_bar = st.progress(0, text="Memulai generate populasi...")

    individu_ke = 0
    while len(population) < population_size:
        individu_ke += 1
        
        if individu_ke > max_retries:
            st.error(
                f"Gagal generate populasi setelah {max_retries} percobaan. "
                f"Hanya berhasil {len(population)}/{population_size} individu. "
                f"Coba naikkan nilai maks percobaan atau periksa data ketersediaan dosen."
            )
            break

        chromosome = [[0] * jumlah_ruangan for _ in range(jumlah_slot)]
        random.shuffle(daftar_mahasiswa)

        gagal = 0
        for id_mhs in daftar_mahasiswa:
            slot_valid = None

            for d in mahasiswa[id_mhs]["dosen"]:
                if slot_valid is None:
                    slot_valid = availability[d].copy()
                else:
                    slot_valid &= availability[d]

            slot_list = list(slot_valid)

            random.shuffle(slot_list)
            ditempatkan = False

            for slot in slot_list:
                if not check_availability(id_mhs, slot, mahasiswa, availability):
                    continue
                room = get_empty_room(chromosome, slot - 1)
                if room is None:
                    continue
                if not check_conflict(chromosome, slot - 1, id_mhs, mahasiswa):
                    continue
                chromosome[slot - 1][room] = id_mhs
                ditempatkan = True
                break

            if not ditempatkan:
                gagal += 1

        if gagal == 0:
            population.append(chromosome)
            pct = len(population) / population_size
            progress_bar.progress(pct, text=f"Individu {len(population)}/{population_size} berhasil digenerate")

    if len(population) == population_size:
        progress_bar.progress(1.0, text=f"Selesai! {population_size} individu berhasil digenerate.")

    return population


def format_schedule_for_display(schedule):
    if hasattr(schedule, "to_array"):
        schedule = schedule.to_array()

    if isinstance(schedule, list):
        formatted = []
        for idx, slot in enumerate(schedule, start=1):
            if isinstance(slot, (list, tuple)):
                formatted.append(f"{idx}: [{', '.join(str(int(value)) for value in slot)}]")
            else:
                formatted.append(f"{idx}: [{int(slot)}]")
        return formatted

    return schedule

def hitung_fitness(schedule):
    """
    Menghitung nilai fitness berdasarkan jumlah sesi kosong di belakang (proposal hal. 15).
    Sesi dihitung kosong jika SELURUH 4 RUANGAN pada sesi tersebut bernilai 0.
    """
    if hasattr(schedule, "to_array"):
        schedule = schedule.to_array()
        
    total_sesi = len(schedule)
    sesi_kosong_di_belakang = 0
    
    for slot_idx in range(total_sesi - 1, -1, -1):
        if all(mhs == 0 for mhs in schedule[slot_idx][:4]):
            sesi_kosong_di_belakang += 1
        else:
            break
            
    return sesi_kosong_di_belakang

def selection_validation(children_population, population_size):
    """
    HANYA mengevaluasi populasi anak (children hasil crossover + mutasi).
    Induk (Parents) dari generasi sebelumnya tidak dimasukkan ke kompetisi generasi baru.
    """
    gabungan_populasi = []
    
    for c in children_population:
        sched = c["schedule"] if isinstance(c, dict) else c
        score = hitung_fitness(sched)
        gabungan_populasi.append({"schedule": sched, "fitness": score, "type": "Child"})
        
    gabungan_populasi.sort(key=lambda x: x["fitness"], reverse=True)
    
    terpilih = gabungan_populasi[:population_size]
    
    return [item["schedule"] for item in terpilih], terpilih

st.title("Sistem Penjadwalan Sidang Menggunakan Genetic Algorithm")

uploaded_availability = st.file_uploader(
    "Upload Availability",
    type=["xlsx"]
)

uploaded_mahasiswa = st.file_uploader(
    "Upload Data Mahasiswa",
    type=["xlsx"]
)

availability = {}
mahasiswa = {}

if uploaded_availability is not None and uploaded_mahasiswa is not None:
    df_availability = pd.read_excel(uploaded_availability)
    df_mahasiswa = pd.read_excel(uploaded_mahasiswa)

    availability = preprocessing_availability(df_availability)
    mahasiswa = preprocessing_mahasiswa(df_mahasiswa)

col1, col2 = st.columns(2)

with col1:
    population_size = st.number_input("Jumlah Populasi", min_value=2, max_value=500, value=15, step=1)

with col2:
    max_generations = st.number_input("Maksimal Iterasi (Generasi)", min_value=10, max_value=500, value=100, step=10)


if st.button("Generate Populasi Awal"):
    if not mahasiswa or not availability:
        st.error("Upload kedua file terlebih dahulu.")
    else:
        population = generate_initial_population(
            population_size,
            mahasiswa,
            availability,
            max_retries=2000 
        )

        st.session_state['parents'] = population
        st.session_state['all_logs'] = [] 
        st.success(f"Populasi berhasil dibuat! ({len(population)} individu)")

st.divider()
st.header("Proses GA")
st.info("Algoritma akan menjalankan seluruh proses (Crossover -> Mutasi -> Seleksi Keturunan) secara otomatis per generasi.")

if st.button("Mulai", type="primary"):
    if 'parents' not in st.session_state or len(st.session_state['parents']) < 2:
        st.error("Silakan generate populasi awal terlebih dahulu di bagian atas!")
    else:
        current_population = st.session_state['parents']
        pop_size = int(population_size)
        
        progress_bar = st.progress(0, text="Memulai evolusi otomatis...")
        status_text = st.empty()
        
        stagnasi_tercapai = False
        generasi_berhenti = 0
        data_lengkap_terakhir = []
        
        stagnation_counter = 0
        best_fitness_history = -1
        
        all_logs = []
        
        for gen in range(int(max_generations)):
            generasi_berhenti = gen + 1
            
            parents_for_this_gen = current_population.copy()
            
            auto_mutation_rate = random.uniform(0.05, 0.10)
            
            children_data, _ = generate_all_children(
                current_population, 
                mahasiswa=mahasiswa, 
                availability=availability,
                debug=False
            )
            
            raw_crossover_schedules = [c["schedule"] if isinstance(c, dict) else c for c in children_data]
            
            mutated_children = []
            mutated_count = 0
            for sched in raw_crossover_schedules:
                new_schedule, is_mutated, _ = swap_mutation(sched, mahasiswa, availability, auto_mutation_rate)
                mutated_children.append(new_schedule)
                if is_mutated:
                    mutated_count += 1
                
            current_population, data_lengkap_terakhir = selection_validation(
                mutated_children, 
                pop_size
            )
            
            best_fitness_current = data_lengkap_terakhir[0]["fitness"] if data_lengkap_terakhir else 0
            
            if best_fitness_current == best_fitness_history:
                stagnation_counter += 1
            else:
                stagnation_counter = 0
                best_fitness_history = best_fitness_current
                
            all_logs.append({
                "gen": generasi_berhenti,
                "parents_schedules": parents_for_this_gen,
                "crossover_count": len(raw_crossover_schedules),
                "crossover_schedules": raw_crossover_schedules,
                "mutation_count": mutated_count,
                "mutation_rate": auto_mutation_rate,
                "mutated_schedules": mutated_children,
                "selection_data": data_lengkap_terakhir,
                "best_fitness": best_fitness_current
            })
            
            pct_complete = generasi_berhenti / int(max_generations)
            progress_bar.progress(
                pct_complete, 
                text=f"Generasi {generasi_berhenti}/{max_generations} | Best Fitness: {best_fitness_current} | Stagnasi: {stagnation_counter}/15"
            )
            
            if stagnation_counter >= 15:
                stagnasi_tercapai = True
                break
                
        
        st.session_state['parents'] = current_population
        st.session_state['all_logs'] = all_logs
        st.session_state['final_ranking'] = data_lengkap_terakhir
        
        if stagnasi_tercapai:
            status_text.success(f"**Evolusi Selesai Lebih Awal!** Algoritma berhenti pada Generasi ke-{generasi_berhenti} karena nilai fitness tertinggi ({best_fitness_history}) stagnan selama 15 generasi berturut-turut.")
        else:
            status_text.success(f"**Evolusi Selesai!** Berhasil menyelesaikan {max_generations} iterasi secara penuh.")

if 'final_ranking' in st.session_state:
    st.subheader(f"Hasil Akhir Jadwal Terbaik")
    
    ranking_data = []
    for rank, item in enumerate(st.session_state['final_ranking'], start=1):
        ranking_data.append({
            "Rank": rank,
            "Fitness Score (Sesi Kosong)": item["fitness"],
            "Jadwal Sesi (Full Array)": str(item["schedule"])
        })
        
    st.dataframe(pd.DataFrame(ranking_data), use_container_width=True)
    
    st.write("Detail Jadwal Terbaik:")
    batas_tampil = len(st.session_state['final_ranking'])
    for i in range(batas_tampil):
        item = st.session_state['final_ranking'][i]
        with st.expander(f'Rank {i+1} (Fitness: {item["fitness"]})'):
            st.code("\n".join(format_schedule_for_display(item["schedule"])))


if 'all_logs' in st.session_state and len(st.session_state['all_logs']) > 0:
    st.divider()
    st.subheader("Log Detail per Generasi")
    
    total_gen_tersedia = len(st.session_state['all_logs'])
    pilihan_gen = st.selectbox(
        "Pilih Generasi untuk melihat detail:", 
        options=range(1, total_gen_tersedia + 1),
        index=total_gen_tersedia - 1 
    )
    
    log_data = st.session_state['all_logs'][pilihan_gen - 1]
    
    st.markdown(f"**Menampilkan Data Generasi ke-{log_data['gen']} | Best Fitness Akhir Gen:** `{log_data['best_fitness']}`")
    
    tab_par, tab_cross, tab_mut, tab_sel = st.tabs(["0. Parent Generasi", "1. Hasil Crossover", "2. Hasil Mutasi", "3. Hasil Seleksi (Top)"])
    
    with tab_par:
        st.write(f"Terdapat **{len(log_data['parents_schedules'])}** individu Parent yang mewariskan gen (digunakan untuk Crossover) pada generasi ini.")
        for i, sched in enumerate(log_data['parents_schedules']):
            with st.expander(f"Parent {i+1}"):
                st.code("\n".join(format_schedule_for_display(sched)))
                
    with tab_cross:
        st.write(f"Dihasilkan **{log_data['crossover_count']}** keturunan baru (Children) dari Parent di atas.")
        for i, sched in enumerate(log_data['crossover_schedules']):
            with st.expander(f"Child {i+1}"):
                st.code("\n".join(format_schedule_for_display(sched)))
                
    with tab_mut:
        st.write(f"Probabilitas Mutasi: **{log_data['mutation_rate']:.2%}**. Terdapat **{log_data['mutation_count']}** individu yang berhasil mengalami Swap Mutation.")
        for i, sched in enumerate(log_data['mutated_schedules']):
            with st.expander(f"Individu Setelah Proses Mutasi {i+1}"):
                st.code("\n".join(format_schedule_for_display(sched)))
                
    with tab_sel:
        st.write("Hasil seleksi yang mengurutkan populasi Keturunan (Child) berdasarkan skor Fitness terbaik. Parent dari generasi sebelumnya telah gugur.")
        for i, item in enumerate(log_data['selection_data']):
            with st.expander(f"Rank {i+1} (Fitness: {item['fitness']})"):
                st.code("\n".join(format_schedule_for_display(item['schedule'])))