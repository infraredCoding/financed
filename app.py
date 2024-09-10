from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/login')
def login():
    return render_template('auth/login.html')


@app.route('/register')
def register():
    return render_template('auth/register.html')


@app.route('/transactions')
def transactions_view():
    return render_template('transactions/transactions.html')


@app.route('/accounts')
def accounts_view():
    return render_template('account/accounts.html')


@app.route('/transaction-templates')
def transaction_templates_view():
    return render_template('transactions/transaction_templates.html')

# dashboard
#   - get all accounts
#       - each acc name, balance
#   - get transactions of last 30 days
#       - acc wise filtering
#       - total income/expense last 30 days
#   - CHARTS

# account
#   - create
#   - update
#   - delete (does not need page)

# transaction
#   - create -
#   - update -
#   - delete (does not need page)
#   - view all --
#   - parse statement

# templates
#   - page view -
#   - create (modal)
#   - update (modal)
#   - delete (modal)


if __name__ == '__main__':
    app.run(debug=True)
