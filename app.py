import os
import uuid
from datetime import datetime

from flask import Flask, render_template, request, url_for, redirect, session
from flask_mysqldb import MySQL
import bcrypt
from werkzeug.utils import secure_filename
import pdfplumber
import re


app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'uploads/'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MYSQL_HOST'] = 'localhost'
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "financed"

mysql = MySQL(app)


def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/')
def hello_world():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    # queries:
    #       - accounts: name, balance
    #       - transactions: last 7 days,
    #       - transactions by category: group by category, get most spent, get top 5 category
    #       - for each month of the month -> get the total spent that year

    cursor = mysql.connection.cursor()
    # accounts
    cursor.execute("""
        SELECT account_name, balance, account_type FROM Account WHERE user_id=%s
    """, (session.get('user_id'),))

    accounts = cursor.fetchall()

    # last 7 days transactions
    cursor.execute("""
            SELECT
                t.transaction_id, t.title, t.date, t.amount, t.category, t.type, a.account_id, a.account_name
            FROM
                Transaction t
                INNER JOIN Account a ON t.account_id = a.account_id
                INNER JOIN User u ON u.user_id = a.user_id
            WHERE u.user_id=%s AND t.date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ORDER BY date DESC
            LIMIT 10;
        """, (session.get('user_id'),))

    transactions = cursor.fetchall()

    cursor.execute("""
        SELECT category, SUM(amount) AS total_expense
        FROM 
            Transaction t
            INNER JOIN Account a ON t.account_id = a.account_id
            INNER JOIN User u ON u.user_id = a.user_id
        WHERE u.user_id=%s AND t.type = 'expense'
        GROUP BY category
        ORDER BY total_expense DESC
        LIMIT 5;
    """, (session.get('user_id'),))

    top_categories = cursor.fetchall()

    cursor.execute("""
        SELECT
            MONTH(date) AS month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS total_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS total_expense
        FROM Transaction t
            INNER JOIN Account a ON t.account_id = a.account_id
            INNER JOIN User u ON u.user_id = a.user_id
        WHERE u.user_id=%s AND YEAR(date) = YEAR(CURDATE())
        GROUP BY MONTH(date)
        ORDER BY MONTH(date);
    """, (session.get('user_id'),))

    month_wise_data = cursor.fetchall()

    net_balance = [0] * 12
    months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    for data in month_wise_data:
        if net_balance[data[0]-1] == 0:
            net_balance[data[0]-1] = data[1] - data[2]

    cursor.close()
    return render_template(
        'dashboard/dashboard.html', accounts=accounts,
        top_categories=top_categories, transactions=transactions, net_balance=net_balance, months=months
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    errors = []

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password').encode('utf-8')

        cursor = mysql.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM User where username=%s; 
            """, (username,)
        )
        data = cursor.fetchone()
        cursor.close()

        if data is None:
            errors.append('User with this username does not exist')
        else:
            db_password = data[2]

            if bcrypt.checkpw(password, db_password.encode('utf-8')):
                session.permanent = True
                session['user_id'] = data[0]
                return redirect(url_for('dashboard'))
            else:
                errors.append('password is incorrect')

    return render_template('auth/login.html', errors=errors)


@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = []
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT username FROM USER WHERE username=%s; 
        """, (username,))

        existing = cursor.fetchone()

        if existing is not None:
            errors.append('User by this username already exists')
            return render_template('auth/register.html', errors=errors)

        if username and password:
            encoded_password = password.encode('utf-8')
            hashed_password = bcrypt.hashpw(encoded_password, bcrypt.gensalt())

            cursor = mysql.connection.cursor()
            cursor.execute(
                """
                INSERT INTO User (username, password) VALUES (%s, %s)
                """, (username, hashed_password)
            )
            mysql.connection.commit()
            cursor.close()
            return redirect(url_for('login'))
    return render_template('auth/register.html', errors=errors)


@app.route('/logout')
def logout():
    # Remove the username from the session
    session.pop('user_id', None)

    # Redirect to the login page or home page
    return redirect(url_for('login'))


@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    errors = []
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        if 'file' not in request.files:
            errors.append('no file detected')
            return redirect(url_for('transactions_view'))
        file = request.files.get('file')
        if file.filename == '':
            errors.append('no file detected')
            return redirect(url_for('transactions_view'))
        if file and file.filename.split('.')[1] == 'pdf':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            with pdfplumber.open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as pdf:
                page = pdf.pages[0]
                text = page.extract_text()

            transaction_re = re.compile(
                r'(?P<Date>\d{2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{2})\s+(?P<TransactionType>[A-Za-z\s]+)\s+(?P<Narration>[A-Za-z0-9\s]+)\s+(?P<Reference>[A-Za-z0-9]+)\s+(?P<ChequeNo>[\w-]+)\s+(?P<Debit>-?\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<Credit>-?\d{1,3}(?:,\d{3})*\.\d{2})\s+(?P<Balance>-?\d{1,3}(?:,\d{3})*\.\d{2})'
            )

            matches = re.finditer(transaction_re, text)

            cursor = mysql.connection.cursor()

            for match in matches:
                title = match.group('Narration')
                debit = match.group('Debit')
                credit = match.group('Credit')
                date = match.group('Date')

                amount = float(credit.replace(',', '')) + float(debit.replace(',', ''))

                t_type = 'income' if amount > 0 else 'expense'

                date_object = datetime.strptime(date, "%d %b %y")
                formatted_date = date_object.strftime("%Y-%m-%d")

                cursor.execute("""
                    INSERT INTO Transaction (transaction_id, title, date, amount, category, type, account_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (f'TX_{str(uuid.uuid4())}', title, formatted_date, abs(amount), title, t_type, account_id))

                mysql.connection.commit()

                if t_type == 'income':
                    cursor.execute("""
                        UPDATE Account SET balance=balance + %s WHERE account_id=%s;
                    """, (abs(amount), account_id))
                    mysql.connection.commit()
                else:
                    cursor.execute("""
                        UPDATE Account SET balance=balance - %s WHERE account_id=%s;
                    """, (abs(amount), account_id))
                    mysql.connection.commit()

            cursor.close()
    return redirect(url_for('transactions_view'))


@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions_view():
    if request.method == 'POST':
        title = request.form.get('title')
        type = request.form.get('type')
        amount = request.form.get('amount')
        date = request.form.get('date')
        category = request.form.get('category')
        account_id = request.form.get('account_id')

        cursor = mysql.connection.cursor()

        if type == 'expense':
            cursor.execute("""
                SELECT balance FROM Account Where account_id=%s;
            """, (account_id,))
            data = cursor.fetchone()[0]

            if (data - float(amount)) >= 0:
                cursor.execute("""
                    INSERT INTO Transaction (transaction_id, title, date, amount, category, type, account_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (f'TX_{str(uuid.uuid4())}', title, date, amount, category, type, account_id))

                mysql.connection.commit()

                cursor.execute("""
                    UPDATE Account SET balance = balance - %s WHERE account_id=%s; 
                """, (amount, account_id,))

                mysql.connection.commit()

        else:
            cursor.execute("""
                INSERT INTO Transaction (transaction_id, title, date, amount, category, type, account_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (f'TX_{str(uuid.uuid4())}', title, date, amount, category, type, account_id))

            mysql.connection.commit()

            cursor.execute("""
                UPDATE Account SET balance = balance + %s WHERE account_id=%s; 
            """, (amount, account_id,))

            mysql.connection.commit()

        cursor.close()

    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        SELECT
            t.transaction_id, t.title, t.date, t.amount, t.category, t.type, a.account_id, a.account_name
        FROM
            Transaction t
            INNER JOIN Account a ON t.account_id = a.account_id
            INNER JOIN User u ON u.user_id = a.user_id
        WHERE u.user_id=%s;
        """, (session.get('user_id'),)
    )

    data = cursor.fetchall()

    cursor.execute(
        """
        SELECT template_id, title, amount, category, type FROM TransactionTemplate WHERE user_id=%s;
        """, (session.get('user_id'),)
    )

    templates = cursor.fetchall()

    cursor.execute("""
        SELECT 
            SUM(CASE WHEN DATE(date) = CURDATE() THEN amount ELSE 0 END) AS total_today,
            SUM(CASE WHEN type = 'income' AND YEAR(date) = YEAR(CURDATE()) AND MONTH(date) = MONTH(CURDATE()) THEN amount ELSE 0 END) AS total_income_this_month,
            SUM(CASE WHEN type = 'expense' AND YEAR(date) = YEAR(CURDATE()) AND MONTH(date) = MONTH(CURDATE()) THEN amount ELSE 0 END) AS total_expense_this_month
        FROM Transaction t
            INNER JOIN Account a ON t.account_id = a.account_id
            INNER JOIN User u ON u.user_id = a.user_id
        WHERE u.user_id=%s;
    """, (session.get('user_id'),))

    summary = cursor.fetchone()

    cursor.execute(
        """
        SELECT a.account_id, a.account_name FROM Account a WHERE a.user_id=%s;
        """, (session.get('user_id'),)
    )

    acc_list = cursor.fetchall()

    cursor.close()
    return render_template(
        'transactions/transactions.html', transactions=data, accounts=acc_list, templates=templates,
        summary=summary
    )


@app.route('/delete-transaction/<string:t_id>', methods=['POST'])
def delete_transaction(t_id):
    if request.method == 'POST':
        cursor = mysql.connection.cursor()

        cursor.execute(""" SELECT account_id, type, amount FROM Transaction WHERE transaction_id=%s;""", (t_id,))

        acc = cursor.fetchone()

        if acc[1] == 'income':
            cursor.execute("""
                UPDATE Account SET balance=balance - %s WHERE account_id=%s;
            """, (acc[2], acc[0]))
            mysql.connection.commit()
        else:
            cursor.execute("""
                UPDATE Account SET balance=balance + %s WHERE account_id=%s;
            """, (acc[2], acc[0]))
            mysql.connection.commit()

        cursor.execute("""
            DELETE FROM Transaction WHERE transaction_id=%s;
        """, (t_id,))

        mysql.connection.commit()
        cursor.close()
    return redirect(url_for('transactions_view'))


@app.route('/accounts', methods=['GET', 'POST'])
@login_required
def accounts_view():
    if request.method == 'POST':
        title = request.form.get('title')
        a_type = request.form.get('type')
        balance = request.form.get('balance')

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO account (user_id, account_name, account_type, balance) values (%s, %s, %s, %s)
        """, (session.get('user_id'), title, a_type, balance))
        mysql.connection.commit()

        cursor.execute("SELECT LAST_INSERT_ID();")
        last_account_id = cursor.fetchone()[0]

        if a_type == 'bank':
            acc_no = request.form.get('b-acc-no')
            name = request.form.get('b-name')
            branch = request.form.get('b-branch')

            # cursor = mysql.connection.cursor()

            cursor.execute("""
                INSERT INTO BankAccount (account_number, bank_name, branch_name, account_id) values (%s, %s, %s)
                    """, (acc_no, name, branch, last_account_id))
            mysql.connection.commit()
            cursor.close()
        elif a_type == 'cash':
            cursor.execute("""
                INSERT INTO Cash (account_id) values (%s)
                """, (last_account_id,))
            mysql.connection.commit()
            cursor.close()
        elif a_type == 'wallet':
            phone = request.form.get('w-phone')
            w_type = request.form.get('w-type')

            cursor.execute("""
                INSERT INTO WalletAccount (phone_number, type, account_id) values (%s, %s, %s)
                """, (phone, w_type, last_account_id,))
            mysql.connection.commit()
            cursor.close()

    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        SELECT
            a.account_id,
            a.account_name,
            a.account_type,
            a.balance,
            
            ba.bank_account_id,
            ba.account_number,
            ba.bank_name,
            ba.branch_name,
            
            wa.wallet_id,
            wa.phone_number,
            wa.type AS wallet_type,
            
            c.cash_id
            
        FROM
            Account a
            
            LEFT JOIN BankAccount ba ON a.account_id = ba.account_id
            
            LEFT JOIN WalletAccount wa ON a.account_id = wa.account_id
            
            LEFT JOIN Cash c ON a.account_id = c.account_id
        WHERE 
            a.user_id = %s;
        """, (session.get('user_id'),)
    )
    data = cursor.fetchall()
    cursor.close()
    return render_template('account/accounts.html', accounts=data)


@app.route('/edit-account/<int:acc_id>', methods=['POST'])
def edit_account(acc_id):
    if request.method == 'POST':
        title = request.form.get('title')
        a_type = request.form.get('type')

        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE account SET account_name=%s, account_type=%s WHERE account_id=%s;
        """, (title, a_type, str(acc_id)))
        mysql.connection.commit()

        if a_type == 'bank':
            acc_no = request.form.get('b-acc-no')
            name = request.form.get('b-name')
            branch = request.form.get('b-branch')

            cursor.execute("""
                UPDATE BankAccount SET account_number=%s, bank_name=%s, branch_name=%s WHERE account_id=%s;
                    """, (acc_no, name, branch, str(acc_id)))
            mysql.connection.commit()
        elif a_type == 'wallet':
            phone = request.form.get('w-phone')
            w_type = request.form.get('w-type')

            cursor.execute("""
                UPDATE WalletAccount SET phone_number=%s, type=%s WHERE account_id=%s;
                """, (phone, w_type, str(acc_id)))
            mysql.connection.commit()
        cursor.close()
    return redirect(url_for('accounts_view'))


@app.route('/delete-account/<int:acc_id>', methods=['POST'])
def delete_account(acc_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT account_id, account_type FROM Account WHERE account_id=%s", (str(acc_id),))
    acc = cursor.fetchone()

    if acc is not None:
        a_type = acc[1]
        if a_type == "bank":
            cursor.execute("DELETE FROM BankAccount WHERE account_id=%s", (str(acc_id),))
            mysql.connection.commit()
        elif a_type == "cash":
            cursor.execute("DELETE FROM Cash WHERE account_id=%s", (str(acc_id),))
            mysql.connection.commit()
        elif a_type == "wallet":
            cursor.execute("DELETE FROM WalletAccount WHERE account_id=%s", (str(acc_id),))
            mysql.connection.commit()

    cursor.execute("DELETE FROM Account WHERE account_id=%s", (str(acc_id),))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('accounts_view'))


@app.route('/transaction-templates', methods=['GET', "POST"])
@login_required
def transaction_templates_view():
    if request.method == 'POST':
        title = request.form.get('title')
        amount = request.form.get('amount')
        category = request.form.get('category')
        t_type = request.form.get('type')

        cursor = mysql.connection.cursor()

        cursor.execute("""
            INSERT INTO TransactionTemplate (title, amount, category, type, user_id)
            VALUES (%s, %s, %s, %s, %s);
        """, (title, amount, category, t_type, session.get('user_id')))

        mysql.connection.commit()

        cursor.close()

    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT template_id, title, amount, category, type FROM TransactionTemplate WHERE user_id=%s;
        """, (session.get('user_id'),)
    )

    data = cursor.fetchall()

    cursor.execute(
        """
        SELECT a.account_id, a.account_name FROM Account a WHERE a.user_id=%s;
        """, (session.get('user_id'),)
    )

    acc_list = cursor.fetchall()

    cursor.close()

    return render_template('transactions/transaction_templates.html', accounts=acc_list, templates=data)


@app.route('/edit-template/<int:template_id>', methods=['POST'])
def edit_template(template_id):
    if request.method == 'POST':
        title = request.form.get('title')
        amount = request.form.get('amount')
        category = request.form.get('category')
        t_type = request.form.get('type')

        cursor = mysql.connection.cursor()

        cursor.execute("""
            UPDATE TransactionTemplate SET title=%s, amount=%s, category=%s, type=%s WHERE template_id=%s;
        """, (title, amount, category, t_type, template_id))

        mysql.connection.commit()
        cursor.close()
    return redirect(url_for('transaction_templates_view'))


@app.route('/delete-template/<int:template_id>', methods=['POST'])
def delete_template(template_id):
    if request.method == 'POST':

        cursor = mysql.connection.cursor()

        cursor.execute("""
            DELETE FROM TransactionTemplate WHERE template_id=%s;
        """, (template_id,))

        mysql.connection.commit()
        cursor.close()
    return redirect(url_for('transaction_templates_view'))


if __name__ == '__main__':
    app.run(debug=True)
