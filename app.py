from flask import Flask, render_template_string, request, redirect, url_for, flash
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-default-key-change-this')

DATA_DIR = '/app/data'
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, 'scores.json')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme123')

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            for player, stats in data.items():
                if 'history' not in stats:
                    matches = stats.get('matches', 0)
                    total_pts = stats.get('total_points', 0.0)
                    if matches > 0 and total_pts != 0:
                        avg_val = total_pts / matches
                        stats['history'] = [round(avg_val, 2)] * matches
                    else:
                        stats['history'] = []
            return data
    except json.JSONDecodeError:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/')
def index():
    data = load_data()
    
    # 1. Calculate global statistics across all players and all matches
    all_points = []
    max_matches = 0
    
    for player, stats in data.items():
        history = stats.get('history', [])
        if len(history) > max_matches:
            max_matches = len(history)
        all_points.extend(history)
    
    # Global mean M
    global_mean = (sum(all_points) / len(all_points)) if all_points else 0.0
    
    # C parameter: 30% of max matches played by the most prolific player
    C = max(0.3 * max_matches, 1.0) if max_matches > 0 else 1.0

    bayesian_leaderboard = []
    raw_leaderboard = []

    for player, stats in data.items():
        history = stats.get('history', [])
        matches = len(history)
        total_points = sum(history)
        raw_avg = (total_points / matches) if matches > 0 else 0.0
        
        # Bayesian Average formula: (C * M + total_points) / (C + matches)
        bayesian_avg = ((C * global_mean) + total_points) / (C + matches) if (C + matches) > 0 else global_mean
        
        p_obj = {
            'name': player,
            'matches': matches,
            'total_points': round(total_points, 2),
            'average': round(raw_avg, 2),
            'bayesian_average': round(bayesian_avg, 2)
        }
        bayesian_leaderboard.append(p_obj)
        raw_leaderboard.append(p_obj)

    # Sort Bayesian leaderboard ascending (lower points = better in penalty games)
    bayesian_leaderboard.sort(key=lambda x: x['bayesian_average'])
    raw_leaderboard.sort(key=lambda x: x['average'])

    # Assign badges for Bayesian Leaderboard: Crown for #1, Skull for the last player
    for i, p in enumerate(bayesian_leaderboard):
        p['rank'] = str(i + 1)
        if i == 0:
            p['badge'] = '👑'
            p['badge_title'] = 'Leader in classifica (Miglior media bayesiana)'
        elif i == len(bayesian_leaderboard) - 1 and len(bayesian_leaderboard) > 1:
            p['badge'] = '💀'
            p['badge_title'] = 'Ultimo in classifica (Peggior media bayesiana)'
        else:
            p['badge'] = ''
            p['badge_title'] = ''

    # Assign ranks for Raw Leaderboard
    for i, p in enumerate(raw_leaderboard):
        p['rank'] = str(i + 1)

    return render_template_string(INDEX_TEMPLATE, 
                                  bayesian_leaderboard=bayesian_leaderboard, 
                                  raw_leaderboard=raw_leaderboard,
                                  global_mean=round(global_mean, 2), 
                                  C=round(C, 2), 
                                  max_matches=max_matches, 
                                  active_tab='bayesian')

@app.route('/history')
def history_view():
    data = load_data()
    leaderboard = []
    max_matches = 0
    for player, stats in data.items():
        history = stats.get('history', [])
        if len(history) > max_matches:
            max_matches = len(history)
        
        matches = len(history)
        total_points = sum(history)
        avg = (total_points / matches) if matches > 0 else 0
        leaderboard.append({
            'name': player,
            'average': round(avg, 2),
            'history': history
        })
    
    leaderboard.sort(key=lambda x: x['average'])
    return render_template_string(HISTORY_TEMPLATE, leaderboard=leaderboard, max_matches=max_matches, active_tab='history')

@app.route('/update', methods=['POST'])
def update_scores():
    password = request.form.get('password', '')
    if password != ADMIN_PASSWORD:
        flash('Password non corretta!', 'danger')
        return redirect(url_for('index'))

    data = load_data()
    names = request.form.getlist('player_name[]')
    points_list = request.form.getlist('player_points[]')

    updated_count = 0
    for name, pts_str in zip(names, points_list):
        name = name.strip()
        if not name:
            continue
        try:
            pts = float(pts_str)
        except ValueError:
            continue

        if name not in data:
            data[name] = {'history': []}
        
        if 'history' not in data[name]:
            matches = data[name].get('matches', 0)
            total_pts = data[name].get('total_points', 0.0)
            if matches > 0:
                data[name]['history'] = [round(total_pts / matches, 2)] * matches
            else:
                data[name]['history'] = []

        data[name]['history'].append(pts)
        data[name].pop('matches', None)
        data[name].pop('total_points', None)
        updated_count += 1

    if updated_count > 0:
        save_data(data)
        flash(f'Punteggi aggiornati con successo per {updated_count} giocatore/i!', 'success')
    else:
        flash('Nessun dato valido inserito.', 'warning')

    return redirect(url_for('index'))

COMMON_NAV = """
<nav class="bg-gray-800 text-white shadow mb-6">
    <div class="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
        <span class="font-bold text-lg">🃏 Card Game Tracker</span>
        <div class="space-x-1 sm:space-x-2">
            <a href="/" class="px-2 sm:px-3 py-2 rounded text-xs sm:text-sm font-medium {% if active_tab == 'bayesian' %}bg-gray-900 text-white{% else %}text-gray-300 hover:bg-gray-700{% endif %}">Classifica Bayesiana</a>
            <a href="/history" class="px-2 sm:px-3 py-2 rounded text-xs sm:text-sm font-medium {% if active_tab == 'history' %}bg-gray-900 text-white{% else %}text-gray-300 hover:bg-gray-700{% endif %}">Storico & Trend</a>
        </div>
    </div>
</nav>
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Card Game Tracker - Classifica Bayesiana</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-100 min-h-screen pb-12">
    """ + COMMON_NAV + """
    <div class="max-w-4xl mx-auto space-y-8 px-4" x-data="{ modalOpen: false, modalText: '', showRaw: false }">
        <header class="text-center">
            <h1 class="text-3xl font-extrabold text-gray-800">Classifica Partite di Carte</h1>
            <p class="text-gray-600 mt-1">Classifica ufficiale basata su Media Bayesiana (C = {{ C }}, Media Globale M = {{ global_mean }})</p>
        </header>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="space-y-2">
              {% for category, message in messages %}
                <div class="p-4 rounded-lg text-white {% if category == 'danger' %}bg-red-500{% elif category == 'success' %}bg-green-500{% else %}bg-yellow-500{% endif %}">
                  {{ message }}
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <!-- Bayesian Leaderboard Table with Horizontal Scroll for Mobile -->
        <div class="bg-white shadow-md rounded-lg overflow-hidden">
            <div class="p-4 bg-gray-900 text-white font-bold flex justify-between items-center">
                <span>🏆 Classifica Ufficiale (Media Bayesiana)</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse whitespace-nowrap">
                    <thead>
                        <tr class="bg-gray-800 text-white">
                            <th class="py-3 px-4">Pos</th>
                            <th class="py-3 px-4">Nome Giocatore</th>
                            <th class="py-3 px-4 text-blue-400">Media Bayesiana</th>
                            <th class="py-3 px-4">Partite Giocate</th>
                            <th class="py-3 px-4">Punti Totali</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for player in bayesian_leaderboard %}
                        <tr class="border-b hover:bg-gray-50">
                            <td class="py-3 px-4 font-bold text-gray-700">{{ player.rank }}</td>
                            <td class="py-3 px-4 font-medium text-gray-900 flex items-center space-x-2">
                                <span>{{ player.name }}</span>
                                {% if player.badge %}
                                <button type="button" @click="modalOpen = true; modalText = '{{ player.badge_title }}'" class="text-lg cursor-pointer focus:outline-none hover:scale-125 transition-transform" title="Clicca per spiegazione">
                                    {{ player.badge }}
                                </button>
                                {% endif %}
                            </td>
                            <td class="py-3 px-4 font-bold text-blue-600 bg-blue-50/50">{{ player.bayesian_average }}</td>
                            <td class="py-3 px-4 text-gray-600">{{ player.matches }}</td>
                            <td class="py-3 px-4 text-gray-600">{{ player.total_points }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="py-6 text-center text-gray-500">Nessun giocatore registrato. Inserisci una partita sotto!</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Popup Modal for Badge Explanation -->
        <div x-show="modalOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50" x-cloak>
            <div @click.away="modalOpen = false" class="bg-white rounded-lg p-6 max-w-sm mx-auto shadow-xl text-center space-y-4">
                <h3 class="text-xl font-bold text-gray-800">Significato dello Stemma</h3>
                <p class="text-gray-600" x-text="modalText"></p>
                <button @click="modalOpen = false" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 font-semibold w-full">Capito!</button>
            </div>
        </div>

        <!-- Score Input Form -->
        <div class="bg-white shadow-md rounded-lg p-6">
            <h2 class="text-xl font-bold text-gray-800 mb-4">Registra Risultati Partita</h2>
            <form action="/update" method="POST" id="match-form" class="space-y-4">
                <div id="player-inputs" class="space-y-3">
                    <div class="flex gap-4 items-center player-row">
                        <input type="text" name="player_name[]" placeholder="Nome Giocatore" required class="flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <input type="number" step="any" name="player_points[]" placeholder="Punti (es. 15 o -5)" required class="w-40 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <button type="button" onclick="removeRow(this)" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-200">Rimuovi</button>
                    </div>
                </div>

                <div class="flex gap-4">
                    <button type="button" onclick="addRow()" class="bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300 font-medium">+ Aggiungi Giocatore</button>
                </div>

                <div class="pt-4 border-t border-gray-200 flex flex-col sm:flex-row gap-4 items-center justify-between">
                    <div class="w-full sm:w-auto flex-1">
                        <input type="password" name="password" placeholder="Password Admin" required class="w-full sm:w-64 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <button type="submit" class="w-full sm:w-auto bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 font-bold">Invia Partita</button>
                </div>
            </form>
        </div>

        <!-- Hidden Raw Average Table Link Section at the Bottom -->
        <div class="text-center pt-4">
            <button @click="showRaw = !showRaw" class="text-blue-600 hover:text-blue-800 underline font-medium text-sm focus:outline-none">
                <span x-text="showRaw ? 'Nascondi la classifica a media reale' : 'Mostra la classifica a media reale (senza correzione bayesiana)'"></span>
            </button>
        </div>

        <!-- Raw Average Table (Collapsible) -->
        <div x-show="showRaw" class="bg-white shadow-md rounded-lg overflow-hidden mt-4" x-cloak>
            <div class="p-4 bg-gray-700 text-white font-bold">📊 Classifica a Media Reale (Senza Correzione)</div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse whitespace-nowrap">
                    <thead>
                        <tr class="bg-gray-200 text-gray-700">
                            <th class="py-3 px-4">Pos</th>
                            <th class="py-3 px-4">Nome Giocatore</th>
                            <th class="py-3 px-4">Media Reale</th>
                            <th class="py-3 px-4">Partite Giocate</th>
                            <th class="py-3 px-4">Punti Totali</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for player in raw_leaderboard %}
                        <tr class="border-b hover:bg-gray-50">
                            <td class="py-3 px-4 font-bold text-gray-700">{{ player.rank }}</td>
                            <td class="py-3 px-4 font-medium text-gray-900">{{ player.name }}</td>
                            <td class="py-3 px-4 font-semibold text-blue-600 bg-blue-50/50">{{ player.average }}</td>
                            <td class="py-3 px-4 text-gray-600">{{ player.matches }}</td>
                            <td class="py-3 px-4 text-gray-600">{{ player.total_points }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function addRow() {
            const container = document.getElementById('player-inputs');
            const row = document.createElement('div');
            row.className = 'flex gap-4 items-center player-row';
            row.innerHTML = `
                <input type="text" name="player_name[]" placeholder="Nome Giocatore" required class="flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <input type="number" step="any" name="player_points[]" placeholder="Punti (es. 15 o -5)" required class="w-40 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <button type="button" onclick="removeRow(this)" class="bg-red-100 text-red-600 px-3 py-2 rounded hover:bg-red-200">Rimuovi</button>
            `;
            container.appendChild(row);
        }

        function removeRow(button) {
            const rows = document.getElementsByClassName('player-row');
            if (rows.length > 1) {
                button.parentElement.remove();
            } else {
                alert("Devi includere almeno un giocatore.");
            }
        }
    </script>
</body>
</html>
"""

HISTORY_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Card Game Tracker - Storico & Trend</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100 min-h-screen pb-12">
    """ + COMMON_NAV + """
    <div class="max-w-5xl mx-auto space-y-8 px-4">
        <header class="text-center">
            <h1 class="text-3xl font-extrabold text-gray-800">Storico e Trend Partite</h1>
            <p class="text-gray-600 mt-1">Dettaglio partita per partita dei punteggi di tutti i giocatori</p>
        </header>

        <!-- Chart Section -->
        <div class="bg-white shadow-md rounded-lg p-6">
            <h2 class="text-xl font-bold text-gray-800 mb-4">Grafico Andamento Punteggi</h2>
            <div class="relative h-80 w-full">
                <canvas id="trendChart"></canvas>
            </div>
        </div>

        <!-- History Table Section -->
        <div class="bg-white shadow-md rounded-lg overflow-hidden">
            <div class="p-4 bg-gray-800 text-white font-bold">Log Partita per Partita</div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse whitespace-nowrap">
                    <thead>
                        <tr class="bg-gray-200 text-gray-700">
                            <th class="py-3 px-4">Nome Giocatore</th>
                            <th class="py-3 px-4">Media</th>
                            {% for i in range(1, max_matches + 1) %}
                            <th class="py-3 px-4 text-center">Partita {{ i }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for player in leaderboard %}
                        <tr class="border-b hover:bg-gray-50">
                            <td class="py-3 px-4 font-bold text-gray-900">{{ player.name }}</td>
                            <td class="py-3 px-4 font-semibold text-blue-600 bg-blue-50/50">{{ player.average }}</td>
                            {% for pts in player.history %}
                            <td class="py-3 px-4 text-center text-gray-700">{{ pts }}</td>
                            {% endfor %}
                            {% for empty in range(player.history|length, max_matches) %}
                            <td class="py-3 px-4 text-center text-gray-300">-</td>
                            {% endfor %}
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="{{ max_matches + 2 }}" class="py-6 text-center text-gray-500">Nessuno storico registrato.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const rawData = {{ leaderboard | tojson }};
        const maxLen = Math.max(...rawData.map(p => p.history.length), 0);
        const labels = Array.from({length: maxLen}, (_, i) => 'Partita ' + (i + 1));

        const colors = [
            '#2563eb', '#dc2626', '#16a34a', '#9333ea', 
            '#ca8a04', '#0d9488', '#db2777', '#4f46e5'
        ];

        const datasets = rawData.map((player, index) => {
            return {
                label: player.name,
                data: player.history,
                borderColor: colors[index % colors.length],
                backgroundColor: colors[index % colors.length],
                tension: 0.1,
                fill: false
            };
        });

        const ctx = document.getElementById('trendChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Punti'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Partite'
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

