#
# sync.py - Max Usachev <maxusachev@gmail.com>
#           Ed Bartosh <bartosh@gmail.com>
#           Peter Bienstman <Peter.Bienstman@UGent.be>

import os
from xml.etree import cElementTree

from mnemosyne.libmnemosyne.tag import Tag
from mnemosyne.libmnemosyne.fact import Fact
from mnemosyne.libmnemosyne.databases.SQLite_logging \
    import SQLiteLogging as events


PROTOCOL_VERSION = 0.1
QA_CARD_TYPE = 1
VICE_VERSA_CARD_TYPE = 2
N_SIDED_CARD_TYPE = 3


class SyncError(Exception):
    pass

class DictClass:
    def __init__(self, attributes=None):
        for attr in attributes.keys():
            setattr(self, attr, attributes[attr])
            
class EventManager:
    
    """Class for manipulatig with client/server database:
    reading/writing history events, generating/parsing
    XML representation of history events.
    
    """

    def __init__(self, mediadir, get_media, ui):
        self.ui = ui
        self.partner = {"id": None, "program_name": None,
            "program_version": None, "protocol_version": None,
            "capabilities": None, "database_name": None,
            "server_deck_read_only": None, "server_allows_media_upload": None}
        self.mediadir = mediadir
        self.get_media = get_media
        self.stopped = False

    def stop(self):
        self.stopped = True

    def set_partner_params(self, partner_params):
        params = cElementTree.fromstring(partner_params) 
        for key in params.keys():
            value = params.get(key)
            if value == "true":
                value = True
            if value == "false":
                value = False
            self.partner[key] = value

    def create_partnership_if_needed(self):
        self.database.create_partnership_if_needed(self.partner["id"])

    def update_last_sync_event(self):
        self.database.update_last_sync_event(self.partner["id"])

    def get_media_count(self):
        return self.database.get_sync_media_count(self.partner["id"])

    def get_history_length(self):
        return self.database.get_sync_history_length(self.partner["id"])

    def get_history(self):

        """Creates history in XML."""
       
        yield str("<history>")
        for item in self.database.get_history_events(self.partner["id"]):
            if self.stopped:
                break
            event = {"event": item[0], "time": item[1], "id": item[2], \
                "s_int": item[3], "a_int": item[4], "n_int": item[5], \
                "t_time": item[6]}
            item = self.create_event_element(event)
            if item:
                yield str(item)
        yield str("</history>")

    def get_media_history(self):

        """Creates media history in XML."""

        history = "<history>"
        for item in self.database.get_media_history_events(self.partner["id"]):
            if self.stopped:
                break
            self.ui.update_events()
            event = {"event": item[0], "id": item[1]}
            if event["event"] in (events.ADDED_MEDIA, events.DELETED_MEDIA):
                history += str(self.create_media_xml_element(event))
        history += "</history>"
        return history

    def create_event_element(self, event):
        event_id = event["event"]
        if event_id in (events.ADDED_TAG, events.UPDATED_TAG, \
            events.DELETED_TAG):
            return self.create_tag_xml_element(event)
        elif event_id in (events.ADDED_FACT, events.UPDATED_FACT, \
            events.DELETED_FACT):
            return self.create_fact_xml_element(event)
        elif event_id in (events.ADDED_CARD, events.UPDATED_CARD, \
            events.DELETED_CARD):
            return self.create_card_xml_element(event)
        elif event_id in (events.ADDED_CARD_TYPE, events.UPDATED_CARD_TYPE, \
            events.DELETED_CARD_TYPE, events.REPETITION):
            return self.create_card_xml_element(event)
        else:
            return None   # No need XML for others events. ?

    def create_tag_xml_element(self, event):
        if event["event"] == events.DELETED_TAG:
            # We only transfer tag id, that should be deleted.
            return "<i><t>tag</t><ev>%s</ev><id>%s</id></i>" % \
                (event["event"], event["id"])
        tag = self.database.get_tag(event["id"], False)
        if not tag:
            return ""
        return "<i><t>tag</t><ev>%s</ev><id>%s</id><name>%s</name></i>" % \
            (event["event"], tag.id, tag.name)

    def create_fact_xml_element(self, event):
        if event["event"] == events.DELETED_FACT:
            # We only transfer fact id, that should be deleted.
            return "<i><t>fact</t><ev>%s</ev><id>%s</id></i>" % \
                (event["event"], event["id"])
        fact = self.database.get_fact(event["id"], False)
        if not fact:
            return ""
        else:
            dkeys = ",".join(["%s" % key for key, val in fact.data.items()])
            dvalues = "".join(["<dv%s><![CDATA[%s]]></dv%s>" % (num, \
            fact.data.values()[num], num) for num in range(len(fact.data))])
            return "<i><t>fact</t><ev>%s</ev><id>%s</id><ctid>%s</ctid><dk>" \
                "%s</dk>%s<tm>%s</tm></i>" % (event["event"], fact.id, \
                fact.card_type.id, dkeys, dvalues, event["time"])

    def create_card_xml_element(self, event):
        if event["event"] == events.DELETED_CARD:
            # We only transfer card id, that should be deleted.
            return "<i><t>card</t><ev>%s</ev><id>%s</id></i>" % \
                (event["event"], event["id"])
        card = self.database.get_card(event["id"], False)
        return "<i><t>card</t><ev>%s</ev><id>%s</id><ctid>%s</ctid><fid>" \
            "%s</fid><fvid>%s</fvid><tags>%s</tags><gr>%s</gr><e>%s</e>" \
            "<lr>%s</lr><nr>%s</nr><si>%s</si><ai>%s</ai><ni>%s</ni>" \
            "<ttm>%s</ttm><tm>%s</tm><_id>%s</_id></i>" % (event["event"], \
            card.id, card.fact.card_type.id, card.fact.id, \
            card.fact_view.id, ",".join([item.name for item in card.tags]),\
            card.grade, card.easiness, card.last_rep, card.next_rep, \
            event["s_int"], event["a_int"], event["n_int"], \
            event["t_time"], event["time"], card._id)
        
    def create_card_type_xml_element(self, event):
        cardtype = self.database.get_card_type(event["id"], False)
        fields = [key for key, value in cardtype.fields]
        return "<i><t>ctype</t><ev>%s</ev><id>%s</id><name>%s</name><f>%s</f>"\
        "<uf>%s</uf><ks>%s</ks><edata>%s</edata></i>" % (event["event"], \
        cardtype.id, cardtype.name, ",".join(fields), \
        ",".join(cardtype.unique_fields), "", "")

    def create_media_xml_element(self, event):
        fname = event["id"].split("__for__")[0]
        if os.path.exists(os.path.join(self.mediadir, fname)):
            return "<i><t>media</t><ev>%s</ev><id>%s</id></i>" % \
                (event["event"], event["id"])
        else:
            return ""

    def create_tag_object(self, item):
        return Tag(item.find("name").text, item.find("id").text)

    def create_fact_object(self, item):
        dkeys = item.find("dk").text.split(",")
        dvals = [item.find("dv%s" % num).text for num in range(len(dkeys))]
        fact_data = dict([(key, dvals[dkeys.index(key)]) for key in dkeys])
        card_type = self.database.get_card_type(\
            item.find("ctid").text, False)
        creation_time = int(item.find("tm").text)
        fact_id = item.find("id").text
        fact = Fact(fact_data, card_type, creation_time, fact_id)
        return fact

    def create_card_object(self, item):
        def get_rep_value(value):
            """Return value for repetition event."""
            if value == "None":
                return ""
            else:
                return int(value)
        return DictClass({"id": item.find("id").text, "fact_view": DictClass(\
            {"id": item.find("fvid").text}), "fact": self.database.get_fact(\
            item.find("fid").text, False), "tags": set(self.database.\
            get_or_create_tag_with_name(tag_name) for tag_name in item.find(\
            "tags").text.split(",")), "grade": int(item.find("gr").text), \
            "easiness": float(item.find("e").text), "acq_reps": 0, "ret_reps": \
            0, "lapses": 0, "acq_reps_since_lapse": 0, "ret_reps_since_lapse": \
            0, "last_rep": int(item.find("lr").text), "next_rep": int(\
            item.find("nr").text), "extra_data": 0, "scheduler_data": 0, \
            "active": True, "in_view": True, "timestamp": int(item.find(\
            "tm").text), "scheduled_interval": get_rep_value(item.find(\
            "si").text), "actual_interval": get_rep_value(item.find(\
            "ai").text), "new_interval": get_rep_value(item.find("ni").text), \
            "thinking_time": get_rep_value(item.find("ttm").text), "_id": \
            item.find("_id").text})

    def create_cardtype_object(self, item):
        return DictClass({"id": item.find("id").text, "name": \
            item.find("name").text, "fields": item.find("f").text.split(","), \
            "keyboard_shortcuts": {}, "extra_data": {}, "unique_fields": \
            item.find("uf").text.split(",")})

    def create_media_object(self, item):
        return None

    def apply_media(self, history, media_count):
        count = 0
        hsize = float(media_count)
        self.ui.show_progressbar()
        for child in cElementTree.fromstring(history):
            self.get_media(child.find("id").text.split("__for__")[0])
            count += 1
            self.ui.update_progressbar(count / hsize)
        self.ui.hide_progressbar()

    def apply_event(self, item):       
        if self.stopped:
            return
        child = cElementTree.fromstring(item)
        event = int(child.find("ev").text)
        if event == events.ADDED_FACT:
            fact = self.create_fact_object(child)
            self.database.add_fact(fact)
        elif event == events.UPDATED_FACT:
            fact = self.database.get_fact(child.find("id").text, False)
            if fact:
                self.database.update_fact(self.create_fact_object(child))
            else:
                self.allow_update_card = False
        elif event == events.DELETED_FACT:
            fact = self.database.get_fact(child.find("id").text, False)
            if fact:
                self.database.delete_fact_and_related_data(fact)
        elif event == events.ADDED_TAG:
            tag = self.create_tag_object(child)
            if not tag.name in self.database.get_tag_names():
                self.database.add_tag(tag)
        elif event == events.UPDATED_TAG:
            self.database.update_tag(self.create_tag_object(child))
        elif event == events.ADDED_CARD:
            card = self.create_card_object(child)
            self.database.add_card(card)
            self.database.log_added_card(int(child.find("tm").text), card.id)
        elif event == events.UPDATED_CARD:
            if self.allow_update_card:
                self.database.update_card(self.create_card_object(child))
            self.allow_update_card = True
        elif event == events.REPETITION:
            old_card = self.database.get_card(child.find("id").text, False)
            new_card = self.create_card_object(child)
            if new_card.timestamp > old_card.last_rep:
                self.database.update_card(new_card)
                self.database.log_repetition(new_card.timestamp, \
                new_card.id, new_card.grade, new_card.easiness, \
                new_card.acq_reps, new_card.ret_reps, new_card.lapses, \
                new_card.acq_reps_since_lapse, \
                new_card.ret_reps_since_lapse, new_card.scheduled_interval,\
                new_card.actual_interval, new_card.new_interval, \
                new_card.thinking_time)