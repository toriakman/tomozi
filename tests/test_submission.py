import tempfile
import unittest
from pathlib import Path

import app as tasting


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous_db = tasting.DB
        tasting.DB = Path(self.directory.name) / 'test.db'
        tasting.init_db()
        self.client = tasting.app.test_client()
        setup = self.client.post('/create', data={'name': 'Test tasting'}).headers['Location']
        self.admin = setup.split('/')[2]
        self.client.post(setup, data={'apple': ['Fuji']})
        self.client.post(f'/host/{self.admin}/status', data={'status': 'OPEN'})
        connection = tasting.db()
        row = connection.execute('SELECT * FROM tastings').fetchone()
        self.join = '/t/' + row['public_token']
        self.results = '/results/' + row['results_token']
        self.apple = connection.execute('SELECT id FROM tasting_apples').fetchone()['id']
        connection.close()
        self.participant = self.client.post(self.join, data={'name': 'Jamie'}).headers['Location']
        self.entry = '/api' + self.participant + '/entry'
        self.confirmation = self.participant + '/submitted'

    def tearDown(self):
        tasting.DB = self.previous_db
        self.directory.cleanup()

    def save(self, rating=8.5, notes='Crisp'):
        return self.client.post(self.entry, json={'tasting_apple_id': self.apple, 'rating': rating, 'notes': notes})

    def submit(self):
        return self.client.post(self.participant + '/submit')

    def test_final_submission_has_separate_confirmation(self):
        self.save()
        response = self.submit()
        self.assertEqual(response.headers['Location'], self.confirmation)
        html = self.client.get(self.confirmation).get_data(as_text=True)
        self.assertIn('Your ratings have been submitted.', html)
        self.assertIn('Your submission is final.', html)
        self.assertNotIn('class="rating"', html)

    def test_saved_and_stale_urls_cannot_edit_submitted_ratings(self):
        self.save()
        self.submit()
        self.assertEqual(self.client.get(self.participant).headers['Location'], self.confirmation)
        self.assertEqual(self.save(1, 'Overwrite').status_code, 409)
        connection = tasting.db()
        entry = connection.execute('SELECT * FROM entries').fetchone()
        self.assertEqual(entry['rating'], 8.5)
        self.assertEqual(entry['notes'], 'Crisp')
        self.assertEqual(connection.execute('SELECT submitted FROM participants').fetchone()[0], 1)
        connection.close()

    def test_repeated_submission_is_safe(self):
        self.save()
        self.submit()
        self.assertEqual(self.submit().headers['Location'], self.confirmation)

    def test_closed_confirmation_offers_results_without_redirecting(self):
        self.save()
        self.submit()
        self.client.post(f'/host/{self.admin}/status', data={'status': 'CLOSED'})
        response = self.client.get(self.confirmation)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Results are in!', html)
        self.assertIn('View results', html)
        self.assertIn('href="' + self.results + '"', html)
        self.assertNotIn('Check for results', html)
        self.assertIn('8.50', self.client.get(self.results).get_data(as_text=True))

    def test_checking_while_open_keeps_waiting_button(self):
        self.save()
        self.submit()
        for _ in range(2):
            response = self.client.get(self.confirmation + '?checked=1')
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn('Not quite yet.', html)
            self.assertIn('check back later', html)
            self.assertIn('Check for results', html)
            self.assertNotIn('View results', html)

    def test_reopening_does_not_unlock_submissions(self):
        self.save()
        self.submit()
        for status in ['CLOSED', 'OPEN']:
            self.client.post(f'/host/{self.admin}/status', data={'status': status})
        self.assertEqual(self.save(2).status_code, 409)
        self.assertEqual(self.client.get(self.confirmation).status_code, 200)

    def test_incomplete_submission_stays_on_rating_page(self):
        self.assertEqual(self.submit().headers['Location'], self.participant)
        self.assertEqual(self.client.get(self.confirmation).headers['Location'], self.participant)
        self.assertEqual(self.save().status_code, 200)

    def test_unsubmitted_ratings_are_not_accepted_after_closing(self):
        self.save()
        self.client.post(f'/host/{self.admin}/status', data={'status': 'CLOSED'})
        self.assertEqual(self.submit().headers['Location'], self.participant)
        self.assertEqual(self.save().status_code, 409)

    def test_unknown_participant_has_no_confirmation(self):
        self.assertEqual(self.client.get('/p/unknown/submitted').status_code, 404)


if __name__ == '__main__':
    unittest.main()
