"""Persistence details for Model Classes"""
import json
import os
from StringIO import StringIO

from flask import current_app
from sqlalchemy import exc

from ..database import db
from ..date_tools import FHIR_datetime
from ..dict_tools import dict_match
from ..models.identifier import Identifier
from ..trace import trace


def require(obj, attr, serial_form):
    """Validation function to assure required attribute is defined"""
    if attr not in serial_form:
        raise ValueError(
            "missing lookup_field {} in serial form of {}".format(
                attr, obj))


class ModelPersistence(object):
    """Adapter class to handle persistence of model tables"""
    VERSION = '0.2'

    def __init__(
            self, model_class, lookup_field='id', sequence_name=None,
            target_dir=None):
        """Initialize adapter for given model class"""
        self.model = model_class
        self.lookup_field = lookup_field
        self.sequence_name = sequence_name
        self.target_dir = target_dir

    def persistence_filename(self):
        """Returns the configured persistence file

        Using the first value found, looks for an environment variable named
        `PERSISTENCE_DIR`, which should define a path relative to the `portal/config`
        directory such as `eproms`.  If no such environment variable is found, use
        the presence of the `GIL` config setting - if set use `gil`,
        else `eproms`.

        :returns: full path to persistence file

        """
        scope = self.model.__name__ if self.model else 'site_persistence_file'

        # product level config file - use presence of env var or config setting
        persistence_dir = os.environ.get('PERSISTENCE_DIR')
        gil = current_app.config.get("GIL")

        # prefer env var
        if not persistence_dir:
            persistence_dir = 'gil' if gil else 'eproms'

        filename = os.path.join(
            os.path.dirname(__file__), persistence_dir, '{scope}.json'.format(
                scope=scope))
        if self.target_dir:
            # Blindly attempt to use target dir if named
            filename = os.path.join(
                self.target_dir, '{scope}.json'.format(scope=scope))
        elif not os.path.exists(filename):
            raise ValueError(
                'File not found: {}  Check value of environment variable `PERSISTENCE_DIR` '
                'Should be a relative path from portal root.'.format(filename))
        return filename

    @staticmethod
    def _log(msg):
        current_app.logger.info(msg)
        trace(msg)

    def __header__(self, data):
        data['resourceType'] = 'Bundle'
        data['id'] = 'SitePersistence v{}'.format(self.VERSION)
        data['meta'] = {'fhir_comments': [
            "export of dynamic site data from host",
            "{}".format(current_app.config.get('SERVER_NAME'))],
            'lastUpdated': FHIR_datetime.now()}
        data['type'] = 'document'
        return data

    def __read__(self):
        self.filename = self.persistence_filename()
        with open(self.filename, 'r') as f:
            try:
                data = json.load(f)
            except ValueError, e:
                msg = "Ill formed JSON in {}".format(self.filename)
                self._log(msg)
                raise ValueError(e, msg)
        self.__verify_header__(data)
        return data

    def __write__(self, data):
        self.filename = self.persistence_filename()
        if data:
            with open(self.filename, 'w') as f:
                f.write(json.dumps(data, indent=2, sort_keys=True, separators=(',', ': ')))
            self._log("Wrote site persistence to `{}`".format(self.filename))

    def __verify_header__(self, data):
        """Make sure header conforms to what we're looking for"""
        if data.get('resourceType') != 'Bundle':
            raise ValueError("expected 'Bundle' resourceType not found")
        if data.get('id') != 'SitePersistence v{}'.format(self.VERSION):
            raise ValueError("unexpected SitePersistence version {}".format(
                data.get('id')))

    def export(self):
        d = self.__header__({})
        d['entry'] = self.serialize()
        self.__write__(data=d)

    def import_(self, keep_unmentioned):
        objs_seen = []
        data = self.__read__()
        for o in data['entry']:
            if not o.get('resourceType') == self.model.__name__:
                # Hard code exception for resourceType: Patient being a User
                if o.get('resourceType') == 'Patient' and self.model.__name__ == 'User':
                    pass
                else:
                    raise ValueError(
                        "Import {} error, Found unexpected '{}' resource".format(
                            self.model.__name__, o.get('resourceType')))
            result = self.update(o)
            db.session.commit()
            if hasattr(result, 'id'):
                objs_seen.append(result.id)
                index_field = 'id'
            else:
                objs_seen.append(getattr(result, self.lookup_field))
                index_field = self.lookup_field

        # Delete any not named
        if not keep_unmentioned:
            query = self.model.query.filter(
                ~getattr(self.model, index_field).in_(
                    objs_seen)) if objs_seen else []
            for obj in query:
                current_app.logger.info(
                    "Deleting {} not mentioned in "
                    "persistence file".format(obj))
            if query:
                query.delete(synchronize_session=False)

        self.update_sequence()
        trace("Import of {} complete".format(self.model.__name__))

    @property
    def query(self):
        """Return ready query to obtain objects for persistence"""
        return self.model.query

    def require_lookup_field(self, obj, serial_form):
        """Validate and return serial form of object"""
        if isinstance(self.lookup_field, tuple):
            for attr in self.lookup_field:
                require(obj, attr, serial_form)
        else:
            require(obj, self.lookup_field, serial_form)
        return serial_form

    def serialize(self):
        if hasattr(self.model, 'as_fhir'):
            serialize = 'as_fhir'
        else:
            serialize = 'as_json'

        results = []

        if isinstance(self.lookup_field, tuple):
            order_col = tuple(
                self.model.__table__.c[field].asc() for field in
                self.lookup_field)
            for item in self.query.order_by(*order_col).all():
                serial_form = self.require_lookup_field(
                    item, getattr(item, serialize)())
                results.append(serial_form)
        else:
            order_col = (
                self.model.__table__.c[self.lookup_field].asc()
                if self.lookup_field != "identifier" else "id")
            for item in self.query.order_by(order_col).all():
                serial_form = self.require_lookup_field(
                    item, getattr(item, serialize)())
                results.append(serial_form)

        return results

    def lookup_existing(self, new_obj, new_data):
        match, field_description = None, None
        if self.lookup_field == 'id':
            field_description = unicode(new_obj.id)
            match = (
                self.model.query.get(new_obj.id)
                if new_obj.id is not None else None)
        elif self.lookup_field == 'identifier':
            ids = new_data.get('identifier')
            if len(ids) == 1:
                id = Identifier.from_fhir(ids[0]).add_if_not_found()
                field_description = unicode(id)
                match = self.model.find_by_identifier(id) if id else None
            elif len(ids) > 1:
                raise ValueError(
                    "Multiple identifiers for {} "
                    "don't know which to match on".format(new_data))
        elif isinstance(self.lookup_field, tuple):
            # Composite key case
            args = {k: new_data.get(k) for k in self.lookup_field}
            field_description = unicode(args)
            match = self.model.query.filter_by(**args).first()
        else:
            args = {self.lookup_field: new_data[self.lookup_field]}
            field_description = getattr(new_obj, self.lookup_field)
            match = self.model.query.filter_by(**args).first()
        return match, field_description

    def update(self, new_data):

        if hasattr(self.model, 'from_fhir'):
            from_method = self.model.from_fhir
            update = 'update_from_fhir'
            serialize = 'as_fhir'
        else:
            from_method = self.model.from_json
            update = 'update_from_json'
            serialize = 'as_json'

        merged = None

        # Generate an empty but complete serialized form of the object
        # so that regardless of shorthand in the persistence file (say
        # ignoring empty fields), a valid representation is available.
        empty_instance = self.model()
        complete_form = getattr(empty_instance, serialize)()
        # Now overwrite any values present in persistence version
        complete_form.update(new_data)
        new_obj = from_method(complete_form)
        existing, id_description = self.lookup_existing(
            new_obj=new_obj, new_data=complete_form)

        if existing:
            details = StringIO()
            if not dict_match(complete_form, getattr(existing, serialize)(), details):
                self._log(
                    "{type} {id} collision on import.  {details}".format(
                        type=self.model.__name__,
                        id=id_description,
                        details=details.getvalue()))
                merged = getattr(existing, update)(complete_form)
            else:
                merged = existing
        else:
            self._log("{type} {id} not found - importing".format(
                type=self.model.__name__,
                id=id_description))
            db.session.add(new_obj)
        return merged or new_obj

    def update_sequence(self):
        """ Bump sequence numbers if necessary

        As the import/update methods don't use the sequences, best
        to manually set it to a value greater than the current max,
        to avoid unique constraint violations in the future.

        """
        if not self.sequence_name:
            return

        max_known = db.engine.execute(
            "SELECT MAX(id) FROM {table}".format(
                table=self.model.__tablename__)).fetchone()[0]
        if max_known:
            db.engine.execute(
                "SELECT SETVAL('{}', {})".format(
                    self.sequence_name, max_known))


class ExclusionPersistence(ModelPersistence):
    """Specialized persistence for exclusive handling

    Manages exclusive details needed when replacing settings from one
    database to another.  For example, prior to pulling a fresh copy
    of production, one retains the configuration of the staging interventions
    such that they'll continue to function as previously configured for
    testing.  Otherwise, interventions would need to use production
    values or re-enter staging configuration values to test every time.

    """
    def __init__(
            self, model_class, limit_to_attributes, filter_query,
            target_dir=None, lookup_field='id',):
        super(ExclusionPersistence, self).__init__(
            model_class=model_class,
            lookup_field=lookup_field,
            sequence_name=None,
            target_dir=target_dir)
        self.limit_to_attributes = limit_to_attributes
        self.filter_query = filter_query

    @property
    def query(self):
        """return ready query to obtain correct set of objects to persist"""
        if not self.filter_query:
            return super(ExclusionPersistence, self).query
        return self.filter_query()

    def require_lookup_field(self, obj, serial_form):
        """Include lookup_field when lacking"""
        results = dict(serial_form)

        if isinstance(self.lookup_field, tuple):
            for attr in self.lookup_field:
                require(obj, attr, serial_form)
            return serial_form

        # As the serialization method is often used for FHIR representation
        # and the object may not typically be handled by persistence, for
        # example with Users, force the lookup field into the serialization
        # form if missing.

        if self.lookup_field not in serial_form:
            results[self.lookup_field] = getattr(obj, self.lookup_field)
        return results

    def update(self, new_data):
        """Strip unwanted attributes before delegating to parent impl"""

        if self.limit_to_attributes is None:
            return super(ExclusionPersistence, self).update(new_data)

        keepers = set(self.limit_to_attributes)
        keepers.add(self.lookup_field)
        desired = {k: v for k, v in new_data.items() if k in keepers}
        return super(ExclusionPersistence, self).update(desired)
