import logging
import math
from contextlib import contextmanager

import click
import psycopg2

from db.connection import close_database, get_engine
from db.ingestion.pipeline import MovieWorker, WorkerOptions
from db.ingestion.store import IngestionStore
from parser.graphql.client import KinopoiskClient
from parser.sitemaps import SitemapClient


logger = logging.getLogger(__name__)


def discover(store: IngestionStore, client: SitemapClient, *, batch_size: int = 5000) -> int:
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError('batch_size must be a positive integer')
    added = 0
    for sitemap in client.catalog_sitemaps():
        batch = []
        found = 0
        for movie_id in client.movie_ids(sitemap):
            batch.append(movie_id)
            found += 1
            if len(batch) >= batch_size:
                added += store.enqueue(batch, source='sitemap', missing_only=True)
                batch.clear()
        if batch:
            added += store.enqueue(batch, source='sitemap', missing_only=True)
        logger.info('Sitemap=%s IDs=%s queued_total=%s', sitemap, found, added)
    return added


def _finite_float(ctx, param, value):
    if not math.isfinite(value):
        raise click.BadParameter('must be a finite number', ctx=ctx, param=param)
    return value


@contextmanager
def _store(*, log_unchanged=False):
    try:
        store = IngestionStore(get_engine(), log_unchanged=log_unchanged)
        store.check_schema()
        yield store
    except KeyboardInterrupt:
        raise click.exceptions.Exit(130) from None
    except psycopg2.Error as error:
        raise click.ClickException(
            f'PostgreSQL error: {type(error).__name__} SQLSTATE={error.pgcode}'
        ) from None
    except click.ClickException:
        raise
    except Exception as error:
        raise click.ClickException(f'{type(error).__name__}: {error}') from None
    finally:
        close_database()


@click.group(
    context_settings={'help_option_names': ['-h', '--help'], 'show_default': True},
    help='Discover and enrich Kinopoisk movies, seasons, episodes and relationships.',
    epilog='Requires migrations through V008. Commands do not apply migrations. '
           'run processes due jobs and exits; invoke it periodically to retry or refresh cards.',
)
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


@main.command('discover', help='Enqueue unknown IDs from public sitemaps.')
@click.option('--batch-size', type=click.IntRange(min=1), default=5000)
def discover_command(batch_size):
    with _store() as store:
        logger.info('Queued %s new IDs', discover(store, SitemapClient(), batch_size=batch_size))


@main.command('refresh', help='Enqueue existing media not yet tracked by ingestion.')
@click.option('--batch-size', type=click.IntRange(min=1), default=5000)
@click.option('--force', is_flag=True, help='Make tracked idle cards due now, including previously processed cards.')
def refresh_command(batch_size, force):
    with _store() as store:
        logger.info('Queued %s existing cards', store.seed_refresh(batch_size=batch_size, force=force))


@main.command('enqueue', help='Enqueue IDs or retry failed jobs explicitly.')
@click.argument('ids', nargs=-1, required=True, type=click.IntRange(min=1))
@click.option('--priority', type=int, default=100)
@click.option('--force', is_flag=True, help='Make existing idle jobs due and reset attempts.')
def enqueue_command(ids, priority, force):
    with _store() as store:
        logger.info('Queued %s IDs', store.enqueue(ids, source='manual', priority=priority, force=force))


@main.command('run', help='Enrich due movie cards, episodes and relationships, then exit.')
@click.option('--workers', type=click.IntRange(min=1), default=4)
@click.option('--rps', type=click.FloatRange(min=0, min_open=True), callback=_finite_float, default=5)
@click.option('--batch-size', type=click.IntRange(min=1), default=500)
@click.option('--flush-seconds', type=click.FloatRange(min=0, min_open=True), callback=_finite_float, default=30)
@click.option('--refresh-days', type=click.FloatRange(min=0, min_open=True), callback=_finite_float, default=14)
@click.option('--max-attempts', type=click.IntRange(min=1), default=8)
@click.option('--max-movies', type=click.IntRange(min=1))
@click.option('--min-votes', type=click.IntRange(min=0),
              help='Insert new media only when Kinopoisk votes exceed this number; missing votes are skipped. '
                   'Existing media are still updated. Skipped IDs are deferred for --refresh-days.')
@click.option('--episodes/--no-episodes', 'include_episodes', default=False,
              help='Fetch and store seasons and episodes when enriching series.')
@click.option('--episode-pages', type=click.IntRange(min=1), default=1000,
              help='Maximum online episode pages per series (20 episodes per page).')
@click.option('--episode-requests', type=click.IntRange(min=0), default=20000,
              help='Maximum individual lookups to fill episodes missing from the online catalog; 0 disables them.')
@click.option('--log-unchanged', is_flag=True, help='Also log cards without data changes.')
def run_command(rps, log_unchanged, **worker_options):
    with _store(log_unchanged=log_unchanged) as store:
        MovieWorker(store, KinopoiskClient(rps=rps), WorkerOptions(**worker_options)).run()


@main.command('status', help='Show queue counts.')
def status_command():
    with _store() as store:
        for state, total, due in store.status():
            logger.info('state=%s total=%s due=%s', state, total, due)


if __name__ == '__main__':
    main()
