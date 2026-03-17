export type { CortexPlayer } from './cortexTypes'

import { sga } from './players/sga'
import { jokic } from './players/jokic'
import { wemby } from './players/wemby'
import { bam } from './players/bam'
import { cade } from './players/cade'
import { white } from './players/white'
import { luka } from './players/luka'
import { curry } from './players/curry'
import { flagg } from './players/flagg'

export const cortexPlayers = [sga, jokic, wemby, bam, cade, white, luka, curry, flagg]
