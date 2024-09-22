CREATE TABLE  User (
user_id INT AUTO_INCREMENT PRIMARY KEY NOT NULL,
username varchar(255) NOT NULL,
password varchar(255) NOT NULL
);

CREATE TABLE  Account (
user_id INT NOT NULL,
account_id INT AUTO_INCREMENT PRIMARY KEY NOT NULL,
account_name varchar(255) NOT NULL,
account_type varchar(255) NOT NULL,
FOREIGN KEY (user_id) REFERENCES User (user_id),
balance FLOAT NOT NULL DEFAULT 0.0
);

CREATE TABLE  BankAccount (
bank_account_id INT AUTO_INCREMENT PRIMARY KEY NOT NULL,
account_number varchar(255) NOT NULL,
bank_name varchar(255) NOT NULL,
branch_name varchar(255),
account_id INT NOT NULL,
FOREIGN KEY (account_id) REFERENCES Account (account_id) ON DELETE CASCADE
);

CREATE TABLE  Cash (
cash_id INT AUTO_INCREMENT PRIMARY KEY NOT NULL,
account_id INT NOT NULL,
FOREIGN KEY (account_id) REFERENCES Account (account_id) ON DELETE CASCADE
);


CREATE TABLE  WalletAccount (
wallet_id INT AUTO_INCREMENT PRIMARY KEY,
phone_number varchar(255) NOT NULL,
type varchar(255) NOT NULL,
account_id INT NOT NULL,
FOREIGN KEY (account_id) REFERENCES Account (account_id) ON DELETE CASCADE
);

CREATE TABLE  Transaction (
transaction_id varchar(255) PRIMARY KEY NOT NULL,
title varchar(255) NOT NULL,
date date NOT NULL,
amount float NOT NULL,
category varchar(255) NOT NULL,
type varchar(255) NOT NULL,
account_id INT NOT NULL,
FOREIGN KEY (account_id) REFERENCES Account (account_id) ON DELETE CASCADE
);

CREATE TABLE  TransactionTemplate (
template_id INT AUTO_INCREMENT PRIMARY KEY,
title varchar(255) NOT NULL,
amount float NOT NULL,
category varchar(255) NOT NULL,
type varchar(255) NOT NULL,
user_id INT NOT NULL,
FOREIGN KEY (user_id) REFERENCES User (user_id) ON DELETE CASCADE
);