import uuid

from flask import Flask, render_template, request, url_for, redirect, session
from flask_mysqldb import MySQL
import bcrypt

app = Flask(__name__)
app.secret_key = 'el_secret_key'

app.config['MYSQL_HOST'] = 'localhost'
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "financed"

mysql = MySQL(app)

@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/dashboard')
def dashboard():
    # queries:
    #       - accounts: name, balance
    #       - transactions: last 7 days,
    #       - transactions by category: group by category, get most spent, get top 5 category
    #       - for each month of the month -> get the total spent that year

    cursor = mysql.connection.cursor()
    # accounts
    cursor.execute("""
        SELECT account_name, balance FROM Account WHERE user_id=%s
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
            WHERE u.user_id=%s;
        """, (session.get('user_id'),))

    cursor.close()
    pass


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
                return redirect(url_for('accounts_view'))
            else:
                errors.append('password is incorrect')

    print(errors)
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # TODO: check if user already exists

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
    return render_template('auth/register.html')


@app.route('/logout')
def logout():
    # Remove the username from the session
    session.pop('user_id', None)

    # Redirect to the login page or home page
    return redirect(url_for('login'))


@app.route('/transactions', methods=['GET', 'POST'])
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

            if (data - float(amount)) > 0:
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
        SELECT a.account_id, a.account_name FROM Account a;
        """
    )

    acc_list = cursor.fetchall()

    cursor.close()
    return render_template('transactions/transactions.html', transactions=data, accounts=acc_list)


@app.route('/delete-transaction/<string:t_id>', methods=['POST'])
def delete_transaction(t_id):
    if request.method == 'POST':
        cursor = mysql.connection.cursor()
        cursor.execute("""
            DELETE FROM Transaction WHERE transaction_id=%s;
        """, (t_id,))
        mysql.connection.commit()
        cursor.close()
    return redirect(url_for('transactions_view'))


@app.route('/accounts', methods=['GET', 'POST'])
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
    print(session.get('user_id'))
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


@app.route('/transaction-templates')
def transaction_templates_view():
    return render_template('transactions/transaction_templates.html')


if __name__ == '__main__':
    app.run(debug=True)
