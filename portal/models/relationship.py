"""Relationship module

Relationship data lives in the `relationships` table, populated via:
    `FLASK_APP=manage.py flask seed`

To extend the list of roles, add name: description pairs to the
STATIC_RELATIONSHIPS dict within, and rerun the seed command above.

"""
from future.standard_library import install_aliases
install_aliases()

from ..database import db
from collections import UserDict


class Relationship(db.Model):
    """SQLAlchemy class for `relationships` table"""
    __tablename__ = 'relationships'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "Relationship {0.name}".format(self)

#Source definition for relationships, as dictionary {name: description,}
STATIC_RELATIONSHIPS = UserDict({
    'partner':
        'An intimate partner relationship',
    'sponsor':
        'The sponsor of a service account.  One way relationship from '
        'the user who created the account (the sponsor) to the service '
        'account used for automatic protected access to API endpoints.',
        })


def enum(**items):
    """Convert dictionary to Enumeration for direct access"""
    return type('Enum', (), items)

RELATIONSHIP = enum(**{str(r).upper():r for r in STATIC_RELATIONSHIPS})


def add_static_relationships():
    """Seed database with default static relationships

    Idempotent - run anytime to pick up any new relationships in existing dbs

    """
    for r in STATIC_RELATIONSHIPS:
        if not Relationship.query.filter_by(name=r).first():
            db.session.add(Relationship(name=r,
                                        description=STATIC_RELATIONSHIPS[r]))
