/*
 * Copyright (c) 2026 MirraNET, Niklas Linz. All rights reserved.
 *
 * This file is part of the MirraNET project and is licensed under the
 * GNU Lesser General Public License v3.0 (LGPLv3).
 *
 * You may use, distribute and modify this code under the terms
 * of the LGPLv3 license. You should have received a copy of the
 * license along with this file. If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>
 * or contact: niklas.linz@mirranet.de
 */

// FreeX for Kodi: packs plugin.video.freex into the zip Kodi installs ("Install from zip file").
// The build agent needs python3 and zip.

pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
        disableConcurrentBuilds()
        timeout(time: 10, unit: 'MINUTES')
    }

    stages {
        stage('Package') {
            steps {
                sh './build.sh'
            }
        }
    }

    post {
        success {
            archiveArtifacts artifacts: 'dist/*.zip', fingerprint: true
        }
    }
}
