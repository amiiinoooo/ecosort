#app.py
import os
import pandas as pd
from datetime import datetime
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, Response
import logging
from flask_mysqldb import MySQL
import matplotlib.pyplot as plt
import numpy 

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-me')

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = 'smartbin_db'

mysql = MySQL(app)
logging.basicConfig(level=logging.DEBUG)

from datetime import datetime

@app.route('/log_data', methods=['POST'])
def log_data():
    compartment_id = request.form['compartment_id']
    weight = request.form['weight']
    logged_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Get current timestamp

    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO compartment_log (compartment_id, weight, logged_at)
        VALUES (%s, %s, %s)
    """, (compartment_id, weight, logged_at))

    mysql.connection.commit()
    return redirect('/dashboard')  # or appropriate redirection

@app.route('/')
def home():
    return redirect('/dashboard')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.environ.get('ADMIN_USER', 'admin') and password == os.environ.get('ADMIN_PASSWORD', ''):
            session['logged_in'] = True
            return redirect('/dashboard')
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/compartments')
def get_compartments():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM compartments")
        rows = cursor.fetchall()

        compartments = []
        for row in rows:
            compartments.append({
                "id": row[0],
                "name": row[1],
                "level_percentage": row[2],
                "weight": row[3],
                "updated_at": row[4]
            })

        return jsonify(compartments)
    except Exception as e:
        logging.error(f"ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/login')

    try:
        cursor = mysql.connection.cursor()

        # Fetch all compartment data
        cursor.execute("SELECT * FROM compartments")
        compartments_data = cursor.fetchall()

        # Fetch bin location
        cursor.execute("SELECT location FROM bin_info WHERE id = 1")
        location_row = cursor.fetchone()
        bin_location = location_row[0] if location_row else "Unknown"

        compartments = []
        total_weight = 0
        alert_count = 0

        # Process compartment data
        for row in compartments_data:
            level = row[2]  # Fill level
            weight = row[3]  # Weight

            # Check if the compartment needs an alert (over 80% full)
            if level >= 80:
                alert_count += 1

            # Append each compartment's data to the compartments list
            compartments.append({
                "id": row[0],
                "name": row[1],
                "level_percentage": level,
                "weight": weight,
                "updated_at": row[4]
            })

            total_weight += weight

        # Fetch total weight per compartment from compartment_log
        total_weight_per_compartment = {}
        for comp in ['Plastic', 'Organic', 'Metal', 'Paper']:
            cursor.execute(f"SELECT SUM(weight) FROM compartment_log WHERE name = %s", (comp,))
            total_weight_per_compartment[comp] = cursor.fetchone()[0] or 0.0

        # Return the dashboard with all the necessary data
        return render_template('dashboard.html',
                               compartments=compartments,
                               total_weight=total_weight,
                               alert_count=alert_count,
                               bin_location=bin_location,
                               total_weight_per_compartment=total_weight_per_compartment)

    except Exception as e:
        logging.error(f"Dashboard error: {e}")
        return f"Error: {e}", 500


@app.route('/history')
def history():
    if not session.get('logged_in'):
        return redirect('/login')

    try:
        # Fetch logs from the database
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT name, weight, level_percentage, logged_at 
            FROM compartment_log 
            ORDER BY logged_at ASC
        """)
        rows = cursor.fetchall()

        # Prepare logs data
        logs = []
        for row in rows:
            logs.append({
                'name': row[0] or "",
                'weight': float(row[1]) if row[1] is not None else 0.0,
                'level_percentage': int(row[2]) if row[2] is not None else 0,
                'logged_at': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else ""
            })

        # Filter logs for today
        logs = [log for log in logs if log['logged_at']]

        # If no logs for today, render an empty history
        if not logs:
            return render_template('history.html', logs=[], fill_level_graph_url='', weight_graph_url='', timestamps=[], poids=[])

        # Prepare data for graphs and chart.js
        timestamps = [datetime.strptime(log['logged_at'], '%Y-%m-%d %H:%M:%S') for log in logs]
        raw_timestamps = [datetime.strptime(log['logged_at'], '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S') for log in logs]

        compartments = ['Plastic', 'Organic', 'Metal', 'Paper']
        weights = {comp: [] for comp in compartments}
        levels = {comp: [] for comp in compartments}

        # Collect data for each compartment
        for log in logs:
            for comp in compartments:
                if log['name'] == comp:
                    weights[comp].append(log['weight'])
                    levels[comp].append(log['level_percentage'])
                else:
                    weights[comp].append(None)
                    levels[comp].append(None)

        # Ensure no None values for weights and levels
        fill_level_data = {comp: [level if level is not None else 0 for level in levels[comp]] for comp in compartments}
        weight_data = {comp: [weight if weight is not None else 0 for weight in weights[comp]] for comp in compartments}

        # Create graphs directory if it doesn't exist
        graph_dir = 'static/graphs'
        os.makedirs(graph_dir, exist_ok=True)

        # Generate Fill Level Graph (Y-axis 0 to 100%)
        plt.figure(figsize=(12, 6))
        for comp, color in zip(compartments, ['blue', 'green', 'red', 'orange']):
            plt.plot(timestamps, fill_level_data[comp], label=f"{comp} Level", marker='o', color=color)
        plt.xlabel('Time')
        plt.ylabel('Fill Level (%)')
        plt.title('SmartBin Fill Levels Over Time')
        plt.xticks(rotation=45)
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
        plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1))
        plt.tight_layout()
        fill_level_graph_path = os.path.join(graph_dir, 'fill_level_graph.png')
        plt.savefig(fill_level_graph_path)
        plt.close()

        # Generate Weight Graph (Y-axis 0 to dynamic max)
        plt.figure(figsize=(12, 6))
        for comp, color in zip(compartments, ['blue', 'green', 'red', 'orange']):
            plt.plot(timestamps, weight_data[comp], label=f"{comp} Weight", marker='o', color=color)
        plt.xlabel('Time')
        plt.ylabel('Weight (g)')
        plt.title('SmartBin Weights Over Time')
        plt.xticks(rotation=45)
        plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
        plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1))
        plt.tight_layout()
        weight_graph_path = os.path.join(graph_dir, 'weight_graph.png')
        plt.savefig(weight_graph_path)
        plt.close()

        # Prepare data for chart.js on the frontend
        timestamps_plastic = []
        poids_plastic = []
        fill_levels_plastic = []

        timestamps_organic = []
        poids_organic = []
        fill_levels_organic = []

        timestamps_metal = []
        poids_metal = []
        fill_levels_metal = []

        timestamps_paper = []
        poids_paper = []
        fill_levels_paper = []
        timestampsss = []

        # Loop through the logs and separate based on the 'name' field
        for row in logs:
            if row['name'] == 'Plastic':
                timestamps_plastic.append(row['logged_at'])
                poids_plastic.append(row['weight'])
                fill_levels_plastic.append(row['level_percentage'])
                timestampsss.append(row['logged_at'])
            elif row['name'] == 'Organic':
                timestamps_organic.append(row['logged_at'])
                poids_organic.append(row['weight'])
                fill_levels_organic.append(row['level_percentage'])
                timestampsss.append(row['logged_at'])
            elif row['name'] == 'Metal':
                timestamps_metal.append(row['logged_at'])
                poids_metal.append(row['weight'])
                fill_levels_metal.append(row['level_percentage'])
                timestampsss.append(row['logged_at'])
            elif row['name'] == 'Paper':
                timestamps_paper.append(row['logged_at'])
                poids_paper.append(row['weight'])
                fill_levels_paper.append(row['level_percentage'])
                timestampsss.append(row['logged_at'])

        return render_template(
            'history.html',
            logs=logs,
            fill_level_graph_url=fill_level_graph_path,
            weight_graph_url=weight_graph_path,
            timestamps=sorted(timestampsss),
            timestamps_plastic=timestamps_plastic,
            poids_plastic=poids_plastic,
            fill_levels_plastic=fill_levels_plastic,
            timestamps_organic=timestamps_organic,
            poids_organic=poids_organic,
            fill_levels_organic=fill_levels_organic,
            timestamps_metal=timestamps_metal,
            poids_metal=poids_metal,
            fill_levels_metal=fill_levels_metal,
            timestamps_paper=timestamps_paper,
            poids_paper=poids_paper,
            fill_levels_paper=fill_levels_paper,
        )

    except Exception as e:
        logging.error(f"History error: {e}")
        return f"Error: {e}", 500






@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_bin(id):
    # Check if the user is logged in, otherwise redirect to the login page
    if not session.get('logged_in'):
        return redirect('/login')

    try:
        # Create a cursor to interact with the database
        cursor = mysql.connection.cursor()

        if request.method == 'POST':
            # Get new values from the form
            name = request.form['name']
            level_percentage = int(request.form['level_percentage'])  # Ensure level_percentage is an integer
            weight_to_add = float(request.form['weight'])  # Weight of trash being added
            updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get the current weight and fill level from the database
            cursor.execute("SELECT weight, level_percentage FROM compartments WHERE id = %s", (id,))
            bin_data = cursor.fetchone()

            if bin_data:
                current_weight = bin_data[0]  # Current weight in the bin
                current_level = bin_data[1]   # Current fill level of the bin

                # Calculate the weight increase based on the weight entered by the user
                weight_increase = weight_to_add  # You can adjust this logic if needed

                # Update the new weight in the compartments table
                new_weight = current_weight + weight_increase

                # Update the compartment's data in the 'compartments' table
                cursor.execute("""
                    UPDATE compartments
                    SET name = %s, level_percentage = %s, weight = %s, updated_at = %s
                    WHERE id = %s
                """, (name, level_percentage, new_weight, updated_at, id))
                mysql.connection.commit()

                # Log the change in the 'compartment_log' (history) table
                cursor.execute("""
                    INSERT INTO compartment_log (compartment_id, name, level_percentage, weight, logged_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id, name, level_percentage, weight_to_add, updated_at))
                mysql.connection.commit()

                # Redirect to the dashboard after successful update
                return redirect('/dashboard')
            else:
                return f"Bin with ID {id} not found", 404

        else:
            # If it's a GET request, retrieve the current data for the specific bin
            cursor.execute("SELECT * FROM compartments WHERE id = %s", (id,))
            bin_data = cursor.fetchone()

            # If bin data is not found, return an error
            if not bin_data:
                return f"Bin with ID {id} not found", 404

            # Current timestamp
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            return render_template('edit.html', bin=bin_data, current_time=current_time)

    except Exception as e:
        # Log the error for debugging
        logging.error(f"Error editing bin with ID {id}: {e}")
        return f"Error: {e}", 500




@app.route('/dashboard1')
def dashboard1():
    cursor = mysql.connection.cursor()

    # Fetch current weight for each compartment
    cursor.execute("SELECT name, weight FROM compartments")
    data = cursor.fetchall()

    compartments = []
    for row in data:
        name = row[0]
        current_weight = row[1]
        
        # Define max capacity for each compartment
        max_capacity = 10  # Example max capacity

        # Calculate the fill percentage
        level_percentage = (current_weight / max_capacity) * 100
        
        # Add to the compartments list
        compartments.append({
            'name': name,
            'weight': current_weight,
            'level_percentage': round(level_percentage, 2),  # rounded to 2 decimal places
        })

    return render_template('dashboard.html', compartments=compartments)

@app.route('/add_waste', methods=['POST'])
def add_waste():
    compartment_id = request.form['compartment_id']
    weight = request.form['weight']

    cursor = mysql.connection.cursor()

    # Insert waste log
    cursor.execute("""
        INSERT INTO compartment_log (compartment_id, weight, logged_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
    """, (compartment_id, weight))
    
    # Update the compartment weight and fill level
    cursor.execute("""
        UPDATE compartments
        SET weight = weight + %s,
            level_percentage = (weight / max_capacity) * 100
        WHERE id = %s
    """, (weight, compartment_id))

    mysql.connection.commit()
    return redirect('/dashboard')

if __name__ == "__main__":
    app.run(debug=True)
