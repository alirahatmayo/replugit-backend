from django.test import TestCase

# Import service tests
from manifest.tests.services.test_upload_service import ManifestUploadServiceTestCase
from manifest.tests.services.test_parser_service import ManifestParserServiceTestCase
from manifest.tests.services.test_mapping_suggestion_service import ManifestMappingSuggestionServiceTestCase
from manifest.tests.services.test_mapping_service import ManifestMappingServiceTestCase
from manifest.tests.services.test_grouping_service import ManifestGroupingServiceTestCase
from manifest.tests.services.test_export_service import ManifestExportServiceTestCase
from manifest.tests.services.test_batch_service import ManifestBatchServiceTestCase

# This file imports all tests from the tests directory
# Tests can be run using the standard Django test command:
# python manage.py test manifest
