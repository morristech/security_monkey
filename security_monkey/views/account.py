#     Copyright 2014 Netflix, Inc.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

from security_monkey.views import AuthenticatedService
from security_monkey.views import __check_auth__
from security_monkey.views import __check_admin__
from security_monkey.views import ACCOUNT_FIELDS
from security_monkey.datastore import Account
from security_monkey.datastore import User
from security_monkey import db

from flask.ext.restful import marshal, reqparse


class AccountGetPutDelete(AuthenticatedService):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        super(AccountGetPutDelete, self).__init__()

    def get(self, account_id):
        """
            .. http:get:: /api/1/account/<int:id>

            Get a list of Accounts matching the given criteria

            **Example Request**:

            .. sourcecode:: http

                GET /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json, text/javascript

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    third_party: false,
                    name: "example_name",
                    notes: null,
                    role_name: null,
                    number: "111111111111",
                    active: true,
                    id: 1,
                    s3_name: "example_name",
                    auth: {
                        authenticated: true,
                        user: "user@example.com"
                    }
                }

            :statuscode 200: no error
            :statuscode 401: Authentication failure. Please login.
        """
        auth, retval = __check_auth__(self.auth_dict)
        if auth:
            return retval

        result = Account.query.filter(Account.id == account_id).first()

        account_marshaled = marshal(result.__dict__, ACCOUNT_FIELDS)
        account_marshaled['auth'] = self.auth_dict

        return account_marshaled, 200

    def put(self, account_id):
        """
            .. http:put:: /api/1/account/1

            Edit an existing account.

            **Example Request**:

            .. sourcecode:: http

                PUT /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json

                {
                    'name': 'edited_account'
                    's3_name': 'edited_account',
                    'number': '0123456789',
                    'notes': 'this account is for ...',
                    'role_name': 'CustomRole',
                    'active': true,
                    'third_party': false
                }

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    'name': 'edited_account'
                    's3_name': 'edited_account',
                    'number': '0123456789',
                    'notes': 'this account is for ...',
                    'role_name': 'CustomRole',
                    'active': true,
                    'third_party': false
                }

            :statuscode 200: no error
            :statuscode 401: Authentication Error. Please Login.
        """

        auth, retval = __check_auth__(self.auth_dict)
        if auth:
            return retval

        if not __check_admin__():
            return {"Error": "You must be an admin to edit accounts"}, 403

        self.reqparse.add_argument('name', required=False, type=unicode, help='Must provide account name', location='json')
        self.reqparse.add_argument('s3_name', required=False, type=unicode, help='Will use name if s3_name not provided.', location='json')
        self.reqparse.add_argument('number', required=False, type=unicode, help='Add the account number if available.', location='json')
        self.reqparse.add_argument('notes', required=False, type=unicode, help='Add context.', location='json')
        self.reqparse.add_argument('role_name', required=False, type=unicode, help='Custom role name.', location='json')
        self.reqparse.add_argument('active', required=False, type=bool, help='Determines whether this account should be interrogated by security monkey.', location='json')
        self.reqparse.add_argument('third_party', required=False, type=bool, help='Determines whether this account is a known friendly third party account.', location='json')
        args = self.reqparse.parse_args()

        account = Account.query.filter(Account.id == account_id).first()
        if not account:
            return {'status': 'error. Account ID not found.'}, 404

        account.name = args['name']
        account.s3_name = args['s3_name']
        account.number = args['number']
        account.notes = args['notes']
        account.role_name = args['role_name']
        account.active = args['active']
        account.third_party = args['third_party']

        db.session.add(account)
        db.session.commit()
        db.session.refresh(account)

        marshaled_account = marshal(account.__dict__, ACCOUNT_FIELDS)
        marshaled_account['auth'] = self.auth_dict

        return marshaled_account, 200

    def delete(self, account_id):
        """
            .. http:delete:: /api/1/account/1

            Delete an account.

            **Example Request**:

            .. sourcecode:: http

                DELETE /api/1/account/1 HTTP/1.1
                Host: example.com
                Accept: application/json

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 202 Accepted
                Vary: Accept
                Content-Type: application/json

                {
                    'status': 'deleted'
                }

            :statuscode 202: accepted
            :statuscode 401: Authentication Error. Please Login.
        """
        auth, retval = __check_auth__(self.auth_dict)
        if auth:
            return retval

        if not __check_admin__():
            return {"Error": "You must be an admin to edit accounts"}, 403

        # Need to unsubscribe any users first:
        users = User.query.filter(User.accounts.any(Account.id == account_id)).all()
        for user in users:
            user.accounts = [account for account in user.accounts if not account.id == account_id]
            db.session.add(user)
        db.session.commit()

        account = Account.query.filter(Account.id == account_id).first()

        db.session.delete(account)
        db.session.commit()

        return {'status': 'deleted'}, 202


class AccountPostList(AuthenticatedService):
    def __init__(self):
        super(AccountPostList, self).__init__()
        self.reqparse = reqparse.RequestParser()

    def post(self):
        """
            .. http:post:: /api/1/account/

            Create a new account.

            **Example Request**:

            .. sourcecode:: http

                POST /api/1/account/ HTTP/1.1
                Host: example.com
                Accept: application/json

                {
                    'name': 'new_account'
                    's3_name': 'new_account',
                    'number': '0123456789',
                    'notes': 'this account is for ...',
                    'role_name': 'CustomRole',
                    'active': true,
                    'third_party': false
                }

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 201 Created
                Vary: Accept
                Content-Type: application/json

                {
                    'name': 'new_account'
                    's3_name': 'new_account',
                    'number': '0123456789',
                    'notes': 'this account is for ...',
                    'role_name': 'CustomRole',
                    'active': true,
                    'third_party': false
                }

            :statuscode 201: created
            :statuscode 401: Authentication Error. Please Login.
        """
        auth, retval = __check_auth__(self.auth_dict)
        if auth:
            return retval

        self.reqparse.add_argument('name', required=True, type=unicode, help='Must provide account name', location='json')
        self.reqparse.add_argument('s3_name', required=False, type=unicode, help='Will use name if s3_name not provided.', location='json')
        self.reqparse.add_argument('number', required=False, type=unicode, help='Add the account number if available.', location='json')
        self.reqparse.add_argument('notes', required=False, type=unicode, help='Add context.', location='json')
        self.reqparse.add_argument('role_name', required=False, type=unicode, help='Custom role name.', location='json')
        self.reqparse.add_argument('active', required=False, type=bool, help='Determines whether this account should be interrogated by security monkey.', location='json')
        self.reqparse.add_argument('third_party', required=False, type=bool, help='Determines whether this account is a known friendly third party account.', location='json')
        args = self.reqparse.parse_args()

        account = Account()
        account.name = args['name']
        account.s3_name = args.get('s3_name', args['name'])
        account.number = args['number']
        account.notes = args['notes']
        account.active = args['active']
        account.third_party = args['third_party']

        db.session.add(account)
        db.session.commit()
        db.session.refresh(account)

        marshaled_account = marshal(account.__dict__, ACCOUNT_FIELDS)
        marshaled_account['auth'] = self.auth_dict
        return marshaled_account, 201

    def get(self):
        """
            .. http:get:: /api/1/accounts

            Get a list of Accounts matching the given criteria

            **Example Request**:

            .. sourcecode:: http

                GET /api/1/accounts HTTP/1.1
                Host: example.com
                Accept: application/json, text/javascript

            **Example Response**:

            .. sourcecode:: http

                HTTP/1.1 200 OK
                Vary: Accept
                Content-Type: application/json

                {
                    count: 1,
                    items: [
                        {
                            third_party: false,
                            name: "example_name",
                            notes: null,
                            role_name: null,
                            number: "111111111111",
                            active: true,
                            id: 1,
                            s3_name: "example_name"
                        },
                    ],
                    total: 1,
                    page: 1,
                    auth: {
                        authenticated: true,
                        user: "user@example.com"
                    }
                }

            :statuscode 200: no error
            :statuscode 401: Authentication failure. Please login.
        """
        auth, retval = __check_auth__(self.auth_dict)
        if auth:
            return retval

        self.reqparse.add_argument('count', type=int, default=30, location='args')
        self.reqparse.add_argument('page', type=int, default=1, location='args')

        args = self.reqparse.parse_args()
        page = args.pop('page', None)
        count = args.pop('count', None)

        result = Account.query.order_by(Account.id).paginate(page, count, error_out=False)

        items = []
        for account in result.items:
            account_marshaled = marshal(account.__dict__, ACCOUNT_FIELDS)
            items.append(account_marshaled)

        marshaled_dict = {
            'total': result.total,
            'count': len(items),
            'page': result.page,
            'items': items,
            'auth': self.auth_dict
        }
        return marshaled_dict, 200
