import unittest

from ct_event_engine.Websites.space_ballroom import SpaceBallroomScraper


class TestSpaceBallroom(unittest.TestCase):

    def test_retrieve_from_source(self):
        events_from_space_ballroom = SpaceBallroomScraper().retrieve_from_source(None)[0]
        self.assertGreater(len(events_from_space_ballroom.events), 0)
        for event in events_from_space_ballroom.events:
            self.assertTrue(len(event.title) != 0)
            self.assertTrue(len(event.begins_on) != 0)
            self.assertTrue(len(event.description) != 0)


if __name__ == '__main__':
    unittest.main()
